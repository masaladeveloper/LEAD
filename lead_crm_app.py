"""Muneer Lead CRM desktop entry point. Business rules live in shared services."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from config import DATABASE_PATH
from crm_database import LeadDatabase, STATUSES
from import_service import import_workbook
from report_service import export_report
from thunderbird_sync import sync_mailboxes
from ui_theme import STYLE


def label(text, name='', wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback, name=''):
    widget = QPushButton(text)
    widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


def panel(name='panel'):
    widget = QFrame()
    widget.setObjectName(name)
    return widget


class Worker(QThread):
    def __init__(self, database_path, operation, parent=None):
        super().__init__(parent)
        self.database_path, self.operation = database_path, operation
        self.result, self.error = None, ""

    def run(self):
        database = None
        try:
            database = LeadDatabase(self.database_path)
            self.result = self.operation(database)
        except Exception as error:
            self.error = str(error)
        finally:
            if database:
                database.close()


class LeadForm(QDialog):
    def __init__(self, parent, lead=None):
        super().__init__(parent)
        self.database = parent.database
        self.lead = lead or {}
        self.setWindowTitle('Edit lead' if lead else 'Add a lead')
        self.resize(680, 730)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label('Lead details' if lead else 'Start a new conversation', 'detailTitle'))
        layout.addWidget(label('Your edits are protected when email sync runs.', 'subtitle'))
        tabs = QTabWidget()
        layout.addWidget(tabs)
        self.fields = {}
        groups = [
            ('Customer', [
                ('customer_name', 'Customer name *', None), ('lead_id', 'Call ID', None),
                ('enquiry_date', 'Enquiry date', None), ('contact_no', 'Phone', None),
                ('email_id', 'Email', None), ('alt_no', 'Alternate phone', None),
                ('city', 'City', None), ('dealer', 'Dealer', None),
                ('model', 'Equipment / model', None), ('quantity', 'Quantity', 'number'),
                ('category', 'Source category', ['', 'Hot', 'Warm', 'Cold']),
                ('voice_of_customer', 'Customer requirement', 'long'),
            ]),
            ('Sales & follow-up', [
                ('status', 'Stage', list(STATUSES)),
                ('follow_up_date', 'Next follow-up', None),
                ('deal_temperature', 'Deal temperature', ['', 'Hot', 'Warm', 'Cold']),
                ('responded', 'Customer response', ['', 'Responded', 'Not Responded', 'No Answer', 'Callback']),
                ('relevance', 'Relevance', ['', 'Relevant', 'Irrelevant']),
                ('remark', 'Sales notes', 'long'),
            ]),
        ]
        for title, fields in groups:
            page = QWidget()
            form = QFormLayout(page)
            form.setContentsMargins(18, 18, 18, 18)
            form.setSpacing(13)
            for key, caption, kind in fields:
                default = {'quantity':'1', 'status':'New', 'dealer':'Muneer Heavy Earthmoving Equipment'}.get(key, '')
                value = str(self.lead.get(key) or default)
                if isinstance(kind, list):
                    widget = QComboBox()
                    widget.addItems(kind)
                    if value not in kind:
                        widget.addItem(value)
                    widget.setCurrentText(value)
                elif kind == 'long':
                    widget = QPlainTextEdit(value)
                    widget.setMaximumHeight(115)
                elif kind == 'number':
                    widget = QSpinBox()
                    widget.setRange(1, 1000000)
                    widget.setValue(int(value))
                else:
                    widget = QLineEdit(value)
                    if key.endswith('date'):
                        widget.setPlaceholderText('YYYY-MM-DD')
                self.fields[key] = widget
                form.addRow(caption, widget)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            tabs.addTab(scroll, title)
        self.initial_values = self.values()
        self.error = label('', wrap=True)
        layout.addWidget(self.error)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self.save)
        actions.rejected.connect(self.reject)
        actions.button(QDialogButtonBox.StandardButton.Save).setObjectName('primary')
        layout.addWidget(actions)

    def values(self):
        values = {}
        for key, widget in self.fields.items():
            if isinstance(widget, QComboBox):
                value = widget.currentText()
            elif isinstance(widget, QPlainTextEdit):
                value = widget.toPlainText()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            else:
                value = widget.text()
            values[key] = value.strip() if isinstance(value, str) else value
        return values

    def save(self):
        values = self.values()
        if not values['customer_name']:
            self.error.setText('Enter a customer name before saving.')
            return
        try:
            with self.database.transaction():
                if self.lead:
                    self.database.update_lead(self.lead['id'], {k:v for k,v in values.items() if v != self.initial_values[k]})
                else:
                    if self.database.find_by_call_id(values['lead_id']):
                        raise ValueError('This Call ID already exists. Open that lead to edit it.')
                    lead_id, created = self.database.upsert_source_lead(values)
                    if not created:
                        raise ValueError('A lead with these contact details already exists.')
                    self.database.update_lead(lead_id, values)
                    self.database.add_activity(lead_id, 'note', 'Lead created manually')
            self.accept()
        except Exception as error:
            self.error.setText(str(error))


class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.database = parent.database
        self.setWindowTitle('Email settings')
        self.resize(700, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(14)
        layout.addWidget(label('Let your inbox do the data entry', 'detailTitle'))
        layout.addWidget(label('Thunderbird downloads the mail. Muneer reads the local folders and keeps your leads up to date.', 'subtitle', True))
        form = QFormLayout()
        self.paths = []
        saved = self.database.mailbox_paths()
        for index, title in enumerate(('Inbox file *', 'Sent file (recommended)')):
            field = QLineEdit(saved[index] if len(saved) > index else '')
            field.setPlaceholderText('Thunderbird mbox file — no .msf extension')
            row = QHBoxLayout()
            row.addWidget(field)
            row.addWidget(button('Browse', lambda checked=False, entry=field: self.browse(entry)))
            form.addRow(title, row)
            self.paths.append(field)
        self.sender = QLineEdit(self.database.get_setting('sender_filter'))
        self.sender.setPlaceholderText('Exact enquiry sender email; separate multiple with commas')
        self.my_email = QLineEdit(self.database.get_setting('my_email'))
        self.my_email.setPlaceholderText('Your sales email address')
        form.addRow('Enquiry sender *', self.sender)
        form.addRow('Your email *', self.my_email)
        self.auto = QCheckBox('Sync automatically when this app is open')
        self.auto.setChecked(self.database.get_setting('auto_sync', '1') == '1')
        form.addRow('', self.auto)
        self.interval = QSpinBox()
        self.interval.setRange(1, 60)
        self.interval.setSuffix(' min')
        self.interval.setValue(self.database.sync_interval_minutes())
        form.addRow('Check every', self.interval)
        layout.addLayout(form)
        layout.addWidget(label('In Thunderbird: Account Settings → Server Settings → Local directory. Select INBOX and Sent (not the .msf index files). Enable offline message downloads. Sent-folder sync captures your replies too.', 'notice', True))
        self.error = label('', wrap=True)
        layout.addWidget(self.error)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        actions.accepted.connect(self.save)
        actions.rejected.connect(self.reject)
        actions.button(QDialogButtonBox.StandardButton.Save).setObjectName('primary')
        layout.addWidget(actions)

    def browse(self, entry):
        path, _ = QFileDialog.getOpenFileName(self, 'Select Thunderbird mailbox file')
        if path:
            entry.setText(path)

    def save(self):
        paths = [entry.text().strip() for entry in self.paths if entry.text().strip()]
        if not self.paths[0].text().strip():
            self.error.setText('Choose your Inbox file.')
            return
        if any(not Path(p).is_file() or p.lower().endswith('.msf') for p in paths):
            self.error.setText('Choose existing mailbox files, not .msf index files.')
            return
        if not self.sender.text().strip() or any('@' not in s for s in self.sender.text().split(',')) or '@' not in self.my_email.text():
            self.error.setText('Enter the enquiry sender address and your sales email address.')
            return
        try:
            with self.database.transaction():
                for key, value in dict(mailbox_paths=json.dumps(paths), sender_filter=self.sender.text().strip(), my_email=self.my_email.text().strip(), auto_sync='1' if self.auto.isChecked() else '0', sync_minutes=str(self.interval.value())).items():
                    self.database.set_setting(key, value)
            self.accept()
        except Exception as error:
            self.error.setText(str(error))


class ReportDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('Export Excel report')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label('Your master, ready to share', 'detailTitle'))
        layout.addWidget(label('Includes current sales notes and email activity.\nDates filter by enquiry date.', 'subtitle'))
        self.scope = QComboBox()
        self.scope.addItems(['Full master', 'Enquiries in a date range'])
        self.start, self.end = QLineEdit(), QLineEdit()
        for widget in (self.start, self.end):
            widget.setPlaceholderText('YYYY-MM-DD')
            widget.setEnabled(False)
        self.scope.currentIndexChanged.connect(lambda i: [w.setEnabled(i == 1) for w in (self.start, self.end)])
        form = QFormLayout()
        form.addRow('Report', self.scope)
        form.addRow('From', self.start)
        form.addRow('Through', self.end)
        layout.addLayout(form)
        self.error = label('')
        layout.addWidget(self.error)
        layout.addWidget(button('Choose file & export', self.save, 'primary'))
        self.selection = None

    def save(self):
        start = self.start.text().strip() if self.scope.currentIndex() else ''
        end = self.end.text().strip() if self.scope.currentIndex() else ''
        if self.scope.currentIndex():
            try:
                if date.fromisoformat(start) > date.fromisoformat(end):
                    raise ValueError
            except ValueError:
                self.error.setText('Enter a valid date range using YYYY-MM-DD.')
                return
        path, _ = QFileDialog.getSaveFileName(self, 'Save Excel report', f'Lead Master - {date.today()}.xlsx', 'Excel workbook (*.xlsx)')
        if path:
            if not path.lower().endswith('.xlsx'):
                path += '.xlsx'
            self.selection = (path, start, end)
            self.accept()


class LeadCRMApp(QMainWindow):
    def __init__(self, database_path=DATABASE_PATH, *, auto_start=True):
        super().__init__()
        self.database = LeadDatabase(database_path)
        self.worker = None
        self.current_filter = 'All leads'
        self.setWindowTitle('Muneer · Lead workspace')
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)
        self._build()
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.sync(manual=False))
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda: self.search_timer.start())
        self.refresh()
        self.configure_timer()
        if auto_start and self.database.get_setting('auto_sync', '1') == '1':
            QTimer.singleShot(500, lambda: self.sync(manual=False))

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(218)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 34, 22, 26)
        side.setSpacing(9)
        side.addWidget(label('muneer', 'brand'))
        side.addWidget(label('THE LEAD WORKSPACE', 'brandSub'))
        side.addSpacing(42)
        side.addWidget(label('WORKSPACE', 'eyebrow'))
        self.navigation = {}
        for caption in ('All leads', 'Open leads', 'Follow-ups due', 'Won'):
            nav = button(caption, lambda checked=False, value=caption: self.set_filter(value), 'nav')
            nav.setCheckable(True)
            nav.setChecked(caption == 'All leads')
            self.navigation[caption] = nav
            side.addWidget(nav)
        side.addSpacing(26)
        side.addWidget(label('TOOLS', 'eyebrow'))
        self.import_button = button('Import Excel', self.import_master, 'nav')
        self.export_button = button('Export report', self.generate_report, 'nav')
        self.settings_button = button('Email settings', self.open_settings, 'nav')
        self.backup_button = button('Back up database', self.backup, 'nav')
        self.rescan_button = button('Rescan email folders', lambda: self.sync(manual=True, force=True), 'nav')
        for item in (self.import_button, self.export_button, self.settings_button, self.backup_button, self.rescan_button):
            side.addWidget(item)
        side.addStretch()
        side.addWidget(label('LOCAL & PRIVATE', 'eyebrow'))
        side.addWidget(label('Your leads stay on this computer.\nMake time for the next conversation.', wrap=True))
        shell.addWidget(sidebar)
        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(32, 28, 32, 24)
        main.setSpacing(20)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(label('SALES / OVERVIEW', 'eyebrow'))
        titles.addWidget(label('Good leads. Better follow-through.', 'title'))
        titles.addWidget(label('A calmer place to turn enquiries into customers.', 'subtitle'))
        header.addLayout(titles)
        header.addStretch()
        self.sync_button = button('Sync now', lambda: self.sync(manual=True))
        header.addWidget(self.sync_button)
        header.addWidget(button('+  Add lead', self.add_lead, 'primary'))
        main.addLayout(header)
        metrics = QHBoxLayout()
        metrics.setSpacing(16)
        self.metrics = {}
        for key, caption, hint in [('total','TOTAL LEADS','Every enquiry, in one place'), ('open_count','IN YOUR PIPELINE','Conversations still open'), ('due','FOLLOW-UPS DUE','Today and overdue'), ('won','DEALS WON','Progress worth keeping')]:
            card = panel('card')
            box = QVBoxLayout(card)
            box.setContentsMargins(20, 17, 20, 17)
            box.addWidget(label(caption, 'eyebrow'))
            self.metrics[key] = label('0', 'metric')
            box.addWidget(self.metrics[key])
            box.addWidget(label(hint, 'subtitle'))
            metrics.addWidget(card)
        main.addLayout(metrics)
        splitter = QSplitter()
        table_panel = panel()
        listing = QVBoxLayout(table_panel)
        listing.setContentsMargins(18, 18, 18, 12)
        controls = QHBoxLayout()
        self.list_title = label('All leads', 'sectionTitle')
        controls.addWidget(self.list_title)
        controls.addStretch()
        self.stage_filter = QComboBox()
        self.stage_filter.addItems(['All leads', 'Open leads', 'Follow-ups due', *STATUSES])
        self.stage_filter.currentTextChanged.connect(self.set_filter)
        controls.addWidget(self.stage_filter)
        listing.addLayout(controls)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search customer, Call ID, phone, model or city…')
        self.search.setClearButtonEnabled(True)
        listing.addWidget(self.search)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['CUSTOMER', 'CALL ID', 'MODEL', 'STAGE', 'FOLLOW-UP', 'ENQUIRY'])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(62)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.show_detail)
        self.table.cellDoubleClicked.connect(lambda row, col: self.edit_selected())
        listing.addWidget(self.table)
        self.empty = label('Your next customer starts here.\nConnect your email or import your existing Excel master.', 'subtitle', True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        listing.addWidget(self.empty)
        self.row_count = label('', 'subtitle')
        listing.addWidget(self.row_count)
        splitter.addWidget(table_panel)
        self.detail = panel()
        self.detail.setMinimumWidth(290)
        detail = QVBoxLayout(self.detail)
        detail.setContentsMargins(18, 18, 18, 18)
        detail.setSpacing(8)
        detail.addWidget(label('LEAD SNAPSHOT', 'eyebrow'))
        self.detail_name = label('Select a lead', 'detailTitle', True)
        self.detail_meta = label('Contact details and activity appear here.', 'subtitle', True)
        self.detail_stage = label('', 'badge')
        detail.addWidget(self.detail_name)
        detail.addWidget(self.detail_meta)
        detail.addWidget(self.detail_stage)
        self.edit_button = button('Edit details / follow-up', self.edit_selected)
        detail.addWidget(self.edit_button)
        detail.addWidget(label('Activity', 'sectionTitle'))
        self.activity_scroll = QScrollArea()
        self.activity_scroll.setWidgetResizable(True)
        detail.addWidget(self.activity_scroll, 1)
        self.note_button = button('+  Log a call / add note', self.add_note)
        detail.addWidget(self.note_button)
        splitter.addWidget(self.detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([760, 320])
        main.addWidget(splitter, 1)
        self.notice = label('Connect your email to start collecting leads automatically.', 'notice', True)
        main.addWidget(self.notice)
        shell.addWidget(content, 1)

    def selected_id(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def set_filter(self, value):
        self.current_filter = value
        self.stage_filter.blockSignals(True)
        self.stage_filter.setCurrentText(value)
        self.stage_filter.blockSignals(False)
        for name, nav in self.navigation.items():
            nav.setChecked(name == value)
        self.list_title.setText(value)
        self.refresh()

    def refresh(self):
        selected = self.selected_id()
        rows = self.database.search(self.search.text(), status=self.current_filter)
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        selected_row = 0
        for index, lead in enumerate(rows):
            values = [lead.get('customer_name') or 'Unnamed', lead.get('lead_id') or '—', lead.get('model') or '—', lead['status'], lead.get('follow_up_date') or '—', lead.get('enquiry_date') or '—']
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, lead['id'])
                item.setToolTip(str(value))
                if column == 3:
                    item.setForeground(QColor('#237760' if value == 'Won' else '#ad5e39' if value in ('New', 'Follow-up') else '#546c76'))
                if column == 0:
                    item.setFont(QFont('Segoe UI', 10, QFont.Weight.DemiBold))
                self.table.setItem(index, column, item)
            if lead['id'] == selected:
                selected_row = index
        if rows:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)
        self.empty.setVisible(not rows)
        self.row_count.setText(f'{len(rows):,} leads shown' + (' · narrow your search to see more' if len(rows) == 10000 else ''))
        for key, count in self.database.counts().items():
            self.metrics[key].setText(f'{count:,}')
        self.show_detail()

    def show_detail(self):
        lead_id = self.selected_id()
        lead = self.database.get_lead(lead_id) if lead_id else None
        for widget in (self.edit_button, self.note_button):
            widget.setEnabled(bool(lead))
        self.detail_name.setText(lead['customer_name'] if lead else 'Select a lead')
        self.detail_meta.setText('\n'.join(filter(None, [lead.get('contact_no'), lead.get('email_id'), ' · '.join(filter(None, [lead.get('city'), lead.get('model')]))])) if lead else 'Contact details and activity appear here.')
        self.detail_stage.setText(lead['status'] if lead else 'No lead selected')
        activity = QWidget()
        activity.setStyleSheet('background: #ffffff;')
        stack = QVBoxLayout(activity)
        stack.setContentsMargins(0, 4, 4, 8)
        stack.setSpacing(14)
        if lead:
            if lead.get('voice_of_customer'):
                stack.addWidget(label('CUSTOMER REQUIREMENT', 'eyebrow'))
                stack.addWidget(label(lead['voice_of_customer'], wrap=True))
            if lead.get('remark'):
                stack.addWidget(label('SALES NOTES', 'eyebrow'))
                stack.addWidget(label(lead['remark'], wrap=True))
            activities = self.database.activities(lead_id)
            for event in activities:
                stack.addWidget(label(f"{event['kind'].upper()} · {event['occurred_at'][:16]}", 'eyebrow', True))
                if event['sender']:
                    stack.addWidget(label(event['sender'], 'subtitle', True))
                stack.addWidget(label(event['body'], wrap=True))
            if not activities:
                stack.addWidget(label('No activity yet. Add a note after your next conversation.', 'subtitle', True))
        stack.addStretch()
        old = self.activity_scroll.takeWidget()
        if old:
            old.deleteLater()
        self.activity_scroll.setWidget(activity)

    def add_lead(self):
        if LeadForm(self).exec():
            self.refresh()

    def edit_selected(self):
        lead_id = self.selected_id()
        if lead_id and LeadForm(self, self.database.get_lead(lead_id)).exec():
            self.refresh()

    def add_note(self):
        lead_id = self.selected_id()
        if not lead_id:
            return
        body, accepted = QInputDialog.getMultiLineText(self, 'Log a conversation', 'Call notes or sales update')
        if accepted and body.strip():
            try:
                self.database.add_activity(lead_id, 'note', body)
                self.show_detail()
            except Exception as error:
                self.notice.setText(f'Could not save note: {error}')

    def configure_timer(self):
        self.timer.stop()
        if self.database.get_setting('auto_sync', '1') == '1':
            self.timer.start(self.database.sync_interval_minutes() * 60000)

    def open_settings(self):
        if SettingsDialog(self).exec():
            self.configure_timer()
            self.sync(manual=True)

    def start_job(self, operation, completed, message):
        if self.worker is not None:
            self.notice.setText('A task is already running. Please wait for it to finish.')
            return False
        self.notice.setText(message)
        for widget in (self.sync_button, self.import_button, self.export_button, self.settings_button, self.backup_button, self.rescan_button):
            widget.setEnabled(False)
        self.worker = Worker(self.database.path, operation, self)
        worker = self.worker
        def finish():
            result, error = worker.result, worker.error
            self.worker = None
            for widget in (self.sync_button, self.import_button, self.export_button, self.settings_button, self.backup_button, self.rescan_button):
                widget.setEnabled(True)
            self.refresh()
            if error:
                self.notice.setText(f'Task failed: {error}')
            else:
                completed(result)
        self.worker.finished.connect(finish)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()
        return True

    def sync(self, manual=False, force=False):
        if self.worker is not None:
            return
        paths = self.database.mailbox_paths()
        sender = self.database.get_setting('sender_filter')
        my_email = self.database.get_setting('my_email')
        if not paths or not sender:
            if manual:
                self.open_settings()
            return
        def operation(database):
            if database.get_setting('last_auto_backup') != date.today().isoformat():
                database.backup()
                database.set_setting('last_auto_backup', date.today().isoformat())
            result = sync_mailboxes(database, paths, sender, my_email, force=force)
            if not result.errors:
                from datetime import datetime
                database.set_setting('last_sync', datetime.now().strftime('%d %b, %H:%M'))
            return result
        def completed(result):
            summary = f'{result.new_leads} new leads · {result.remarks_added} email updates'
            if result.errors:
                self.notice.setText(summary + ' · Needs attention: ' + ' | '.join(result.errors))
            else:
                auto = 'Auto-sync on while app is open' if self.database.get_setting('auto_sync', '1') == '1' else 'Auto-sync off'
                text = f"Synced {self.database.get_setting('last_sync')} · {summary} · {auto}"
                if result.unparsed:
                    text += f' · {result.unparsed} enquiry emails could not be parsed'
                if result.pending:
                    text += f' · {result.pending} replies awaiting a matching lead'
                self.notice.setText(text)
        self.start_job(operation, completed, 'Reading your mailbox folders… you can keep working.')

    def import_master(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import existing leads', '', 'Excel workbook (*.xlsx)')
        if path:
            self.start_job(lambda database: import_workbook(database, path), lambda result: self.notice.setText(f'Imported {result.added} new leads · refreshed {result.updated} existing leads · your sales notes were preserved. Backup: {result.backup}'), 'Importing your workbook and creating a backup…')

    def generate_report(self):
        dialog = ReportDialog(self)
        if dialog.exec() and dialog.selection:
            path, start, end = dialog.selection
            self.start_job(lambda database: export_report(database, path, start, end), lambda count: self.notice.setText(f'Exported {count} leads to {path}'), 'Preparing your Excel report…')

    def backup(self):
        self.start_job(lambda database: database.backup(), lambda path: self.notice.setText(f'Backup saved: {path}'), 'Backing up the master database…')

    def closeEvent(self, event):
        if self.worker is not None:
            self.notice.setText('Finishing the current task. Please close the app again once it completes.')
            event.ignore()
            return
        self.timer.stop()
        self.database.close()
        event.accept()


def main():
    smoke_test = '--smoke-test' in sys.argv
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setApplicationName('Muneer Lead CRM')
    window = LeadCRMApp(auto_start=not smoke_test)
    window.show()
    if smoke_test:
        # Exercise the real Qt entry point without reading mail or waiting for input.
        window.timer.stop()
        QTimer.singleShot(500, window.close)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
