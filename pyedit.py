import sys
import os
import subprocess
import ast
import importlib
from PyQt5.QtWidgets import (
QMainWindow, QApplication, QTextEdit, QAction, QFileDialog, QMenu, QVBoxLayout, QWidget, QSplitter,
QFontDialog, QPlainTextEdit
)
from PyQt5.QtGui import QIcon, QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QTextCursor, QPainter, QTextFormat
from PyQt5.QtCore import QRegExp, Qt, QRect, QSize



class PyEditHighLighter(QSyntaxHighlighter):
    def __init__(self,document):
        super().__init__(document)
        self.imported_modules = {}
        self.failed_modules = set()
        self.module_names = set()
        self.variable_occurences = {}
        self.lines = 0

        self.module_format_success = QTextCharFormat()
        self.module_format_success.setForeground(QColor(0,0,128))#Mavi

        self.function_format_failure = QTextCharFormat()
        self.function_format_failure.setForeground((QColor(255,0,0)))#Kırmızı

        self.function_format_success = QTextCharFormat()
        self.function_format_success.setForeground(QColor(0,128,0))#Yeşil

        self.variable_format_declaration = QTextCharFormat()
        self.variable_format_declaration.setForeground(QColor(255,165,0))#Turuncu

        self.variable_format_usage = QTextCharFormat()
        self.variable_format_usage.setForeground(QColor(128,0,128))#Mor

        self.keywords = ['def','class','if','else','while','return','for','try','except','as','in']
        self._highlighting_rules = []
        for word in self.keywords:
            pattern = r'\b'+word+r'\b'
            self._highlighting_rules.append((QRegExp(pattern),self.module_format_success))

        builtin_functions = [
            'print', 'len', 'range', 'input', 'int', 'float', 'str', 'list', 'dict', 'set', 'tuple',
            'open', 'close', 'sum', 'min', 'max', 'sorted', 'reversed', 'enumerate', 'map', 'filter',
            'zip', 'abs', 'round', 'pow', 'help', 'dir', 'isinstance', 'issubclass', 'getattr', 'setattr'
        ]
        for function in builtin_functions:
            pattern = r'\b'+function+ r'\b(?=\()'
            self._highlighting_rules.append((pattern,self.function_format_success))

    def highlightBlock(self,text):
        cursor = self.document().findBlock(self.currentBlock().position())
        block_number = cursor.blockNumber() + 1
        self.lines = block_number
        for pattern, format in self._highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >=0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text,index+length)
        self.highlight_imported_modules_and_functions(text)
        self.highlight_strings(text)
        self.parse_code_with_ast(text)
        self.highlight_variables(text)

    def highlight_imported_modules_and_functions(self,text):
        for module_name in self.module_names:
            module_pattern = r'\b'+module_name+r'\b'
            expression = QRegExp(module_pattern)
            index = expression.indexIn(text)
            while index >=0:
                length = expression.matchedLength()
                self.setFormat(index,length,self.module_format_success)
                index = expression.indexIn(text,index+length)

        for module_name in self.failed_modules:
            module_pattern = r'\b'+module_name+r'\b'
            expression = QRegExp(module_pattern)
            index = expression.indexIn(text)
            while index >=0:
                length = expression.matchedLength()
                self.setFormat(index,length,self.function_format_failure)
                index = expression.indexIn(text,index+length)
        self.highlight_module_functions(text)

    def highlight_module_functions(self,text):
        module_function_pattern = r'\b(\w+)\.(\w+)\s*(?=\()' #time.time()
        expression = QRegExp(module_function_pattern)
        index = expression.indexIn(text)

        while index >=0:
            module_name = expression.cap(1)
            function_name = expression.cap(2)
            if module_name in self.imported_modules:
                module = self.imported_modules[module_name]
                if hasattr(module,function_name):
                    function_start = expression.pos(2)
                    self.setFormat(function_start,len(function_name),self.function_format_success)
                else:
                    function_start = expression.pos(2)
                    self.setFormat(function_start, len(function_name), self.function_format_failure)
            index = expression.indexIn(text, index + expression.matchedLength())
    def highlight_strings(self,text):
        string_pattern = r'".*?"|\'.*?\''
        expression = QRegExp(string_pattern)
        index = expression.indexIn(text)
        while index >= 0:
            length = expression.matchedLength()
            self.setFormat(index, length, QTextCharFormat())
            index = expression.indexIn(text, index + length)
    def parse_code_with_ast(self,code):
        try:
            tree= ast.parse(code)
            self.analyze_ast(tree)
        except Exception as e:
            print(e)
    def analyze_ast(self,tree):
        if not hasattr(self,'variable_lines'):
            self.variable_lines = {}

        for node in ast.walk(tree):
            try:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_name = target.id

                            block_text = self.currentBlock().text()
                            single_quote_positions = [i for i, char in enumerate(block_text) if char=="'"]
                            double_quote_positions = [i for i, char in enumerate(block_text) if char == '"']
                            all_quotes = sorted(single_quote_positions+double_quote_positions)

                            variable_start = block_text.find(var_name)
                            variable_end = variable_start + len(var_name)

                            if any(start <= variable_start < end or start < variable_end <= end for start, end in zip(all_quotes[::2], all_quotes[1::2])):
                                continue
                            elif var_name not in self.variable_lines:
                                self.variable_lines[var_name] = self.lines
                if isinstance(node,ast.Import):
                    for alias in node.names:
                        self.load_module(alias.name)
                elif isinstance(node,ast.ImportFrom):
                    self.load_module(node.module)
            except Exception as e:
                print(e)

    def load_module(self,module_name):
        if module_name not in self.imported_modules and module_name not in self.failed_modules:
            try:
                module = importlib.import_module(module_name)
                self.imported_modules[module_name] = module
                self.module_names.add(module_name)
            except ImportError:
                self.failed_modules.add(module_name)

    def highlight_variables(self,text):
        try:
            single_quote_positions = [i for i, char in enumerate(text) if char == "'"]
            double_quote_positions = [i for i, char in enumerate(text) if char == '"']
            all_quotes = sorted(single_quote_positions + double_quote_positions)

            if len(all_quotes) >=2:
                start_of_highlight = all_quotes[1] + 1
            else:
                start_of_highlight = 0

            assignment_pattern = r'\b(\w+)\s*=' # a = 5
            expression = QRegExp(assignment_pattern)
            index = expression.indexIn(text)
            while index >=0:
                length = expression.matchedLength()
                variable_name = expression.cap(1)
                variable_start = index
                variable_end = variable_start + len(variable_name)

                if any(start <= variable_start < end or start < variable_end <= end for start, end in
                       zip(all_quotes[::2], all_quotes[1::2])):
                    index = expression.indexIn(text, index + length)
                    continue

                current_line = self.currentBlock().blockNumber() + 1
                if variable_name not in self.variable_lines:
                    self.variable_lines[variable_name] = current_line

                if index >= start_of_highlight:
                    self.setFormat(index,len(variable_name), self.variable_format_declaration)
                index = expression.indexIn(text,index + length)
            for var_name, line_number in self.variable_lines.items():
                var_pattern = r'\b'+var_name+r'\b'
                expression = QRegExp(var_pattern)
                index = expression.indexIn(text)

                while index >=0:
                    length = expression.matchedLength()
                    current_line = self.currentBlock().blockNumber() + 1
                    if current_line==line_number:
                        self.setFormat(index, length, self.variable_format_declaration)
                    elif index >= start_of_highlight:
                        self.setFormat(index,length,self.variable_format_usage)
                    index = expression.indexIn(text,index+length)
        except Exception as a:
            print(a)

class LineNumberArea(QWidget):
    def __init__(self,editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(),0)
    def paintEvent(self,event):
        self.code_editor.line_number_area_paint_event(event)

class CustomTextEdit(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)
        self.update_line_number_area_width(0)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.setFont(QFont('Consolas',16))
        self.highlight_current_line()
    def line_number_area_width(self):
        digits = len(str(self.blockCount()))
        space = 10 + self.fontMetrics().width('9') * digits
        return space
    def update_line_number_area_width(self,_):
        self.setViewportMargins(self.line_number_area_width(),0,0,0)
    def update_line_number_area(self,rect,dy):
        if dy:
            self.line_number_area.scroll(0,dy)
        else:
            self.line_number_area.update(0,rect.y(),self.line_number_area_width(),rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    def line_number_area_paint_event(self,event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(),QColor(46,46,46))
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()

        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number+1)
                painter.setPen(QColor(200,200,200))
                painter.drawText(0,int(top) - 2, self.line_number_area.width() - 5, int(self.fontMetrics().height()),Qt.AlignRight,number)
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
    def resizeEvent(self,event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(QRect(cr.left(),cr.top(),self.line_number_area_width(),cr.height()))
    def highlight_current_line(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(75,0,130,50)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection,True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        self.setExtraSelections(extra_selections)
    def keyPressEvent(self,event):
        cursor = self.textCursor()
        if event.key()==Qt.Key_Tab:
            self.insertPlainText("    ")
        elif event.key()==Qt.Key_Return:
            current_block_text = cursor.block().text()
            leading_spaces = len(current_block_text) - len(current_block_text.lstrip(' '))
            if ':' in current_block_text.strip():
                leading_spaces += 4
            super().keyPressEvent(event)
            self.insertPlainText(' '*leading_spaces)
        elif event.key()==Qt.Key_ParenLeft:
            self.insertPlainText('()')
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
        elif event.key()==Qt.Key_BraceLeft:
            self.insertPlainText('{}')
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
        elif event.key()==Qt.Key_BracketLeft:
            self.insertPlainText('[]')
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
        elif event.key()==Qt.Key_QuoteDbl:
            self.insertPlainText('""')
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
        elif event.key()==Qt.Key_Apostrophe:
            self.insertPlainText("''")
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
        else:
            super().keyPressEvent(event)

class IDE(QMainWindow):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        container = QWidget()
        container.setLayout(main_layout)
        splitter = QSplitter(Qt.Vertical)
        self.setWindowTitle('PyEdit')
        self.setWindowIcon(QIcon('icon.ico'))
        self.setGeometry(300,300,800,600)
        self.text_edit = CustomTextEdit(self)
        splitter.addWidget(self.text_edit)
        self.output_area = QTextEdit(self)
        self.output_area.setReadOnly(True)
        splitter.addWidget(self.output_area)
        main_layout.addWidget(splitter)
        self.setCentralWidget(container)
        self.highlighter = PyEditHighLighter(self.text_edit.document())
        self.init_ui()
    def init_ui(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu('File')
        open_file_action = QAction(QIcon('icon.ico'),'Open',self)
        open_file_action.triggered.connect(self.open_file)
        file_menu.addAction(open_file_action)
        save_file_action = QAction(QIcon('icon.ico'), 'Open', self)
        save_file_action.triggered.connect(self.save_file)
        file_menu.addAction(save_file_action)
        run_action = QAction(QIcon(),'Run',self)
        run_action.triggered.connect(self.run_code)
        menu_bar.addAction(run_action)
        settings_menu = menu_bar.addMenu('Settings')
        font_action = QAction('Font Settings',self)
        font_action.triggered.connect(self.open_font_dialog)
        settings_menu.addAction(font_action)
        self.text_edit.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text_edit.customContextMenuRequested.connect(self.show_context_menu)
        self.apply_dark_theme()
        self.output_area.append("Output:\n")
        self.show()



    def open_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self,'Open File','','Python Files (*.py);;All Files (*)')
        if file_name:
            try:
                with open(file_name,'r',encoding='utf-8') as file:
                    self.text_edit.setPlainText(file.read())
            except Exception as e:
                print(e)
    def save_file(self):
        file_name, _ = QFileDialog.getSaveFileName(self,'Save File','','Python Files (*.py)')
        if file_name:
            if not file_name.endswith('.py'):
                file_name += '.py'
            try:
                with open(file_name, 'w') as file:
                    file.write(self.text_edit.toPlainText())
            except Exception as e:
                print(e)
    def run_code(self):
        code = self.text_edit.toPlainText()
        process = subprocess.Popen(['python','-c',f"import sys; sys.stdout.reconfigure(encoding='utf-8');{code}"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        self.output_area.clear()
        if output:
            self.output_area.append("Output:\n"+output.decode('utf-8',errors='ignore'))
        if error:
            self.output_area.append("Error:\n" + error.decode('utf-8', errors='ignore'))
    def open_font_dialog(self):
        font,ok = QFontDialog.getFont()
        if ok:
            self.text_edit.setFont(font)
    def show_context_menu(self,position):
        context_menu = QMenu()
        run_action = QAction('Run',self)
        run_action.triggered.connect(self.run_code)
        context_menu.addAction(run_action)
        context_menu.exec_(self.text_edit.mapToGlobal(position))
    def apply_dark_theme(self):
        dark_theme = """
        QMainWindow {
            background-color: #1e1e1e;
        }

        QTextEdit, QPlainTextEdit {
            background-color: #2e2e2e;
            color: #dcdcdc;
            font: 16px 'Consolas';
            border: 1px solid #4b0082;
        }

        QMenuBar {
            background-color: #2e2e2e;
            color: #dcdcdc;
        }

        QMenuBar::item:selected {
            background-color: #4b0082;
        }

        QMenu {
            background-color: #2e2e2e;
            color: #dcdcdc;
        }

        QMenu::item:selected {
            background-color: #4b0082;
        }

        QPushButton {
            background-color: #4b0082;
            color: #ffffff;
            border-radius: 5px;
            padding: 5px;
        }

        QPushButton:hover {
            background-color: #6a0dad;
        }

        QScrollBar:vertical {
            border: 1px solid #4b0082;
            background: #2e2e2e;
            width: 15px;
            margin: 22px 0 22px 0;
        }

        QScrollBar::handle:vertical {
            background: #4b0082;
            min-height: 20px;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: #4b0082;
            height: 20px;
            subcontrol-origin: margin;
        }

        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        """
        self.setStyleSheet(dark_theme)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ide = IDE()
    sys.exit(app.exec_())