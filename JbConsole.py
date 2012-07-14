#!/usr/bin/env jython
##############################################################################
# Copyright (c) 2009,2012 Hajime Nakagami<nakagami@gmail.com>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 
#   1. Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
# 
#   2. Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
##############################################################################
import sys, pickle
from java.lang import *
from javax.swing import *
from java.awt.event import *
from java.awt import *
from javax.swing.event import *
from javax.swing.tree import *
from javax.swing.table import *
from java.util.prefs import Preferences
import fbutil

APP_NAME = 'JbConsole'
__version__ = '0.2.0'
files = ('root', 'server', 'database', 'domain', 'object', 'function', 
    'generators', 'generator', 'procedures', 'procedure', 
    'systemtables', 'systemtable', 'tables', 'table', 
    'trigger', 'trigger_inact', 'view', 'down', 'key', 'column',)
icons = dict(zip(files, [ImageIcon('./res/' + f + '.png') for f in files]))

PK_COLOR = Color(0xFF, 0xFF, 0x80)
FK_COLOR = Color(0x00, 0xFF, 0x00)
PK_FK_COLOR = Color(0xC0, 0xFF, 0x80)
UK_COLOR = Color(0x80, 0x80, 0x80)

def head_titles(h):
    return [s.title().replace('_', ' ') for s in h]

charset_list = ("UNICODE_FSS", "NONE", "ASCII", "UTF8", "OCTETS", 
        #from fbintl.conf <charset ????>
        "SJIS_0208", "EUCJ_0208", "DOS437", "DOS850", "DOS865",
        "ISO8859_1", "ISO8859_2", "ISO8859_3", "ISO8859_4", "ISO8859_5",
        "ISO8859_6", "ISO8859_7", "ISO8859_8", "ISO8859_9", "ISO8859_13",
        "DOS852", "DOS857", "DOS860", "DOS861", "DOS863", "CYRL", "DOS737", 
        "DOS775", "DOS858", "DOS862", "DOS864", "DOS866", "DOS869",
        "WIN1250", "WIN1251", "WIN1252", "WIN1253", "WIN1254", "NEXT",
        "WIN1255", "WIN1256", "WIN1257", "KSC_5601", "BIG_5", "GB_2312",
        "KOI8R", "KOI8U", "WIN1258", "TIS620", "GBK", "CP943C",
    )


menu = [
    ['SERVERS', 'Server', KeyEvent.VK_S, [
        ['REG_SERVER', 'Add Server', KeyEvent.VK_A],
        ['UNREG_SERVER', 'Remove Server', KeyEvent.VK_R],
        ['EDIT_SERVER', 'Edit Server info', KeyEvent.VK_E],
        None,
        ['QUIT', 'Quit', KeyEvent.VK_Q],
      ]
    ],
    ['DATABASES', 'Databases', KeyEvent.VK_D, [
        ['REG_DB', 'Register Exsisting Database', KeyEvent.VK_D],
        ['UNREG_DB', 'Unregister Database', KeyEvent.VK_U],
        ['EDIT_DB', 'Edit Connect Parameter', KeyEvent.VK_E],
        None,
        ['OPEN_DB', 'Open Database', KeyEvent.VK_O],
        ['CLOSE_DB', 'Close Database', KeyEvent.VK_C],
        ['ISQL', 'Interactive SQL', KeyEvent.VK_I],
        None,
        ['TABLE_INFO', 'Table', KeyEvent.VK_T, [
            ['TABLE_CONSTRAINTS', 'Show Constraints', KeyEvent.VK_C],
            ['SHOW_INDEX', 'Show Index', KeyEvent.VK_X],
            ['SHOW_REFERENCED_COLUMN', 'Show Referenced Table', KeyEvent.VK_R],
          ]
        ],
        ['VIEW_SOURCE', 'View Source', KeyEvent.VK_V],
        ['SHOW_GRANT', 'Show Grant Users', KeyEvent.VK_U],
      ]
    ],
    ['HELP', 'Help', KeyEvent.VK_H, [
        ['ABOUT', 'About', KeyEvent.VK_A],
      ]
    ]
]


def adjust_column_width(table):
    columnModel = table.getColumnModel()
    for col in range(table.getColumnCount()):
        maxwidth = 0
        for row in range(table.getRowCount()):
            rend = table.getCellRenderer(row, col)
            width = rend.getTableCellRendererComponent(table,
                    table.getValueAt(row, col), False, False, row, col
                    ).getPreferredSize().width
            if maxwidth < width:
                maxwidth = width
        columnModel.getColumn(col).setPreferredWidth(maxwidth)


class ConnParam(object):   # Keep connection parameter without hostname.
    def __init__(self, path, user, password = None, charset='UNICODE_FSS',
                                        port = 3050, save_password=False):
        self.path = path
        self.user = user
        self.password = password
        self.charset = charset
        self.port = port
        self.save_password = save_password

def dialog_layout(dlg, parent):
    p_size = parent.getSize()
    p_loc = parent.getLocation()
    size = dlg.getSize()
    x = p_loc.x + p_size.width/2 - size.width/2
    y = p_loc.y + p_size.height/2 - size.height/2
    if x < 0: x = 0
    if y < 0: y = 0
    dlg.setLocation(x, y)

class SqlDialog(JDialog, ActionListener):
    def __init__(self, parent, db):
        JDialog.__init__(self, parent, "Interactive SQL", True)
        self.db = db
        self.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE)
        bar = JToolBar()
        b = JButton(icons['down'])
        b.addActionListener(self)
        bar.add(b)
        self.add(bar, BorderLayout.NORTH)
        self.text = JTextArea()
        self.text.setRows(5)
        self.split = JSplitPane(JSplitPane.VERTICAL_SPLIT, True, 
                            JScrollPane(self.text), JScrollPane(JTable()))
        self.add(self.split)
        self.pack()
        dialog_layout(self, parent)
        self.setVisible(True)

    def actionPerformed(self, ae):
        try:
            h, d = self.db.execute(self.text.getText())
            table = JTable(d, head_titles(h))
            self.split.setBottomComponent(JScrollPane(table))
        except Exception, e:
            text = JTextArea(str(e))
            text.setEditable(False)
            self.split.setBottomComponent(JScrollPane(text))


class ConnParamDialog(JDialog, ActionListener):
    def __init__(self, parent, conn_param = None):
        JDialog.__init__(self, parent, "Connection Parameter", True)
        self.conn_param = None
        self.setDefaultCloseOperation(JFrame.DISPOSE_ON_CLOSE)
        self.setResizable(False)
        self.setLayout(GridLayout(4, 1))

        pathPanel = JPanel()
        pathPanel.setLayout(BoxLayout(pathPanel, BoxLayout.X_AXIS))
        pathPanel.add(JLabel(' Path: '))
        self._text_path = JTextField(40)
        self._text_path.setMaximumSize(self._text_path.getPreferredSize())
        pathPanel.add(self._text_path)
        b = JButton("...")
        b.setActionCommand("FILE_CHOOSER")
        b.addActionListener(self)
        pathPanel.add(b)

        userPanel = JPanel()
        userPanel.setLayout(BoxLayout(userPanel, BoxLayout.X_AXIS))
        userPanel.add(JLabel(' User: '))
        self._text_user = JTextField(16)
        self._text_user.setMaximumSize(self._text_user.getPreferredSize())
        userPanel.add(self._text_user)
        userPanel.add(JLabel(' Password: '))
        self._text_password = JPasswordField(16)
        self._text_password.setMaximumSize(
                    self._text_password.getPreferredSize())
        userPanel.add(self._text_password)

        miscPanel = JPanel()
        miscPanel.setLayout(BoxLayout(miscPanel, BoxLayout.X_AXIS))
        miscPanel.add(JLabel(' Charecter Set: '))
        self._combo_charset= JComboBox(charset_list)
        self._combo_charset.setMaximumSize(
                    self._combo_charset.getPreferredSize())
        miscPanel.add(self._combo_charset)
        miscPanel.add(JLabel(' Port: '))
        self._text_port = JTextField(5)
        self._text_port.setMaximumSize(self._text_port.getPreferredSize())
        miscPanel.add(self._text_port)
        self._check_savepass = JCheckBox('Save Password')
        miscPanel.add(self._check_savepass)

        buttonPanel = JPanel()
        b = JButton("OK")
        b.setActionCommand("OK")
        b.addActionListener(self)
        buttonPanel.add(b)
        b = JButton("CANCEL")
        b.setActionCommand("CANCEL")
        b.addActionListener(self)
        buttonPanel.add(b)

        self.add(pathPanel)
        self.add(userPanel)
        self.add(miscPanel)
        self.add(buttonPanel)
        self.pack()
        if conn_param:
            self._text_path.setText(conn_param.path)
            self._text_user.setText(conn_param.user)
            self._text_password.setText(conn_param.password)
            self._check_savepass.setSelected(conn_param.save_password)
            self._combo_charset.setSelectedItem(conn_param.charset)
            self._text_port.setText(str(conn_param.port))
        else:
            self._text_port.setText('3050')

        dialog_layout(self, parent)
        self.setVisible(True)

    def actionPerformed(self, ae):
        ac = ae.getActionCommand()
        if ac == 'OK' or ac == 'CANCEL':
            if ac == 'OK':
                self.conn_param = ConnParam(self._text_path.getText(),
                    self._text_user.getText(), self._text_password.getText(),
                    charset = self._combo_charset.getSelectedItem(),
                    port = int(self._text_port.getText()),
                    save_password = self._check_savepass.isSelected())
            self.setVisible(False)
            self.dispose()
        elif ac == 'FILE_CHOOSER':
            dlg = JFileChooser()
            if dlg.showOpenDialog(self) == JFileChooser.APPROVE_OPTION:
                self._text_path.setText(dlg.getSelectedFile().getPath())


class TreeNode(Object):
    def __init__(self, name, node_type):
        self.name = name
        self.node_type = node_type
    def toString(self):
        return self.name


class ColumnTableCellRenderer(DefaultTableCellRenderer):
    def __init__(self, pk, fk, uk):
        self.pk = pk
        self.fk = fk
        self.uk = uk
    def getTableCellRendererComponent(self, t, v, i, h, row, col):
        DefaultTableCellRenderer.getTableCellRendererComponent(
                                                    self, t, v, i, h, row, col)
        s = t.getModel().getValueAt(row, 0)
        if (s in self.pk) and (s in self.fk):
            self.setBackground(PK_FK_COLOR)
        elif s in self.pk:
            self.setBackground(PK_COLOR)
        elif s in self.fk:
            self.setBackground(FK_COLOR)
        elif s in self.uk:
            self.setBackground(UK_COLOR)
        else:
            self.setBackground(t.getBackground())
        return self


class ShowIndexTableCellRenderer(DefaultTableCellRenderer):
    def getTableCellRendererComponent(self, t, v, i, h, row, col):
        DefaultTableCellRenderer.getTableCellRendererComponent(
                                                    self, t, v, i, h, row, col)
        s = t.getModel().getValueAt(row, 2)
        if s == 'PRIMARY KEY':
            self.setBackground(PK_COLOR)
        elif s == 'FOREIGN KEY':
            self.setBackground(FK_COLOR)
        elif s == 'UNIQUE':
            self.setBackground(UK_COLOR)
        return self
ShowConstraintsTableCellRenderer = ShowIndexTableCellRenderer

class JbTreeCellRenderer(DefaultTreeCellRenderer):
    icon_map = {'ROOT' : icons['root'],
                'SERVER' : icons['server'], 
                'DOMAINS' : icons['domain'],
                'EXCEPTIONS' : icons['object'],
                'FUNCTIONS' : icons['function'],
                'GENERATORS' : icons['generators'],
                'PROCEDURES' : icons['procedures'],
                'PROCEDURE' : icons['procedure'],
                'ROLES' : icons['object'],
                'ROLE' : icons['object'],
                'DATABASE' : icons['database'],
                'SYSTEMTABLES' : icons['systemtables'],
                'SYSTEMTABLE' : icons['systemtable'],
                'TABLES' : icons['tables'],
                'TABLE' : icons['table'],
                'TRIGGERS' : icons['trigger'],
                'TRIGGER' : icons['trigger'],
                'TRIGGER_INACT' : icons['trigger_inact'],
                'VIEWS' : icons['view'],
                'VIEW' : icons['view'],
    }
    def getTreeCellRendererComponent(self, t, v, s, e, l, r, h):
        c = DefaultTreeCellRenderer.getTreeCellRendererComponent(
                                                self, t, v, s, e, l, r, h)
        icon = self.icon_map.get(v.getUserObject().node_type)
        if icon:
            c.setIcon(icon)
        return c

class TreeMouseListener(MouseAdapter):
    def __init__(self, frame):
        self.frame = frame

    def mouseClicked(self, me):
        if not SwingUtilities.isLeftMouseButton(me) or me.getClickCount() != 2:
            return
        path = self.frame.tree.getSelectionPath()
        if not path:
            return
        c = path.getLastPathComponent()
        node = c.getUserObject()
        if node.node_type != 'DATABASE':
            return
        if hasattr(node, 'db') and node.db:
            return
        param = node.conn_param
        if param.password == None:
            pwd = JPasswordField(10)
            if JOptionPane.showConfirmDialog(self.frame, pwd,
                    "Enter %s's password" % (param.user), 
                    JOptionPane.YES_NO_OPTION) == JOptionPane.YES_OPTION:
                param.password = String(pwd.getPassword())
            else:
                return
        node.db = fbutil.FbDatabase(host=c.getParent().getUserObject().name,
                    path=param.path, user=param.user, password=param.password,
                    charset=param.charset, port=param.port)
        try:
            node.db.open()
        except Exception, e:
            node.db = None
            JOptionPane.showMessageDialog(self.frame, str(e), 
                            "Can't Open Database", JOptionPane.ERROR_MESSAGE)
        self.frame.update_menu_tree(c)
        self.frame.tree.updateUI()

class MainFrame(JFrame, ActionListener, TreeSelectionListener):
    def update_menu_tree(self, path_comp):
        node = path_comp.getUserObject()

        if node.node_type == 'ROOT':
            self.menu['REG_SERVER'].setEnabled(True)
        else:
            self.menu['REG_SERVER'].setEnabled(False)
            parent_type = path_comp.getParent().getUserObject().node_type
            if parent_type == 'TABLES' or parent_type == 'SYSTEMTABLES':
                self.menu['TABLE_INFO'].setEnabled(True)
            else:
                self.menu['TABLE_INFO'].setEnabled(False)

        if node.node_type == 'SERVER':
            self.menu['UNREG_SERVER'].setEnabled(True)
            self.menu['EDIT_SERVER'].setEnabled(True)
            self.menu['REG_DB'].setEnabled(True)
        else:
            self.menu['UNREG_SERVER'].setEnabled(False)
            self.menu['EDIT_SERVER'].setEnabled(False)
            self.menu['REG_DB'].setEnabled(False)

        if node.node_type == 'DATABASE':
            self.menu['EDIT_DB'].setEnabled(True)
            self.menu['UNREG_DB'].setEnabled(True)
            if hasattr(node, "db") and getattr(node, "db"): # Opened
                self.menu['OPEN_DB'].setEnabled(False)
                self.menu['CLOSE_DB'].setEnabled(True)
                self.menu['ISQL'].setEnabled(True)
                if not path_comp.getChildCount():
                    nk = [('Domains', 'DOMAINS'), ('Exceptions', 'EXCEPTIONS'), 
                      ('Functions', 'FUNCTIONS'), ('Generators', 'GENERATORS'),
                      ('Procedures', 'PROCEDURES'), ('Roles', 'ROLES'),
                      ('System Tables', 'SYSTEMTABLES'), ('Tables', 'TABLES'),
                      ('Triggers', 'TRIGGERS'), ('Views', 'VIEWS')]
                    for (n, k) in nk:
                        path_comp.add(DefaultMutableTreeNode(TreeNode(n, k)))
            else:                                           # Closed
                self.menu['OPEN_DB'].setEnabled(True)
                self.menu['CLOSE_DB'].setEnabled(False)
                self.menu['ISQL'].setEnabled(False)
                path_comp.removeAllChildren()
        else:
            self.menu['EDIT_DB'].setEnabled(False)
            self.menu['UNREG_DB'].setEnabled(False)
            self.menu['OPEN_DB'].setEnabled(False)
            self.menu['CLOSE_DB'].setEnabled(False)
            self.menu['ISQL'].setEnabled(False)

        if (node.node_type == 'TABLE' or node.node_type == 'VIEW'
                                            or node.node_type == 'PROCEDURE'):
            self.menu['SHOW_GRANT'].setEnabled(True)
        else:
            self.menu['SHOW_GRANT'].setEnabled(False)
        if node.node_type == 'PROCEDURE' or node.node_type == 'VIEW':
            self.menu['VIEW_SOURCE'].setEnabled(True)
        else:
            self.menu['VIEW_SOURCE'].setEnabled(False)

    def save_pref(self):
        pref = {}
        loc = self.getLocation()
        pref['X'] = loc.x
        pref['Y'] = loc.y
        size = self.getSize()
        pref['WIDTH'] = size.width
        pref['HEIGHT'] = size.height
        pref['DIVIDER'] = self.split.getDividerLocation()

        tree = []
        root = self.tree.getModel().getRoot()
        for i in range(root.getChildCount()):
            snode = root.getChildAt(i)
            params=[]
            for j in range(snode.getChildCount()):
                param = snode.getChildAt(j).getUserObject().conn_param
                if not param.save_password:
                    param.password = None   # Clear password
                params.append(param)
            tree.append([snode.toString(), params])
        pref['TREE'] = tree

        prefs = Preferences.userRoot().node('/org/nakagami/jbconsole')
        s = pickle.dumps(pref)
        prefs.put(APP_NAME, s) 
        prefs.flush()

    def load_pref(self):
        try:
            self.pref = pickle.loads(
                Preferences.userRoot().node('/org/nakagami/jbconsole').get(APP_NAME, None))
        except:
            self.pref = {}
        self.pref.setdefault('X', 0)
        self.pref.setdefault('Y', 0)
        self.pref.setdefault('WIDTH', 800)
        self.pref.setdefault('HEIGHT', 600)
        self.pref.setdefault('DIVIDER', 200)
        self.pref.setdefault('TREE', [])

    def quit_app(self, e):
        self.save_pref()
        self.dispose()

    def __init__(self):
        self.windowClosing = self.quit_app
        self.title = APP_NAME
        self.load_pref()

        self.menu = {}
        jmb = JMenuBar()
        for m in menu:
            jm = JMenu(m[1])
            jm.setActionCommand(m[0])
            jm.setMnemonic(m[2])
            self.menu[m[0]] = jm
            for mi in m[3]:
                if mi and len(mi) == 3:
                    jmi = JMenuItem(mi[1])
                    jmi.setActionCommand(mi[0])
                    jmi.setMnemonic(mi[2])
                    jmi.addActionListener(self)
                    self.menu[mi[0]] = jmi
                    jm.add(jmi)
                elif mi and len(mi) == 4:   # Sub Menu
                    jmi = JMenu(mi[1])
                    jmi.setActionCommand(mi[0])
                    jmi.setMnemonic(mi[2])
                    jmi.addActionListener(self)
                    self.menu[mi[0]] = jmi
                    jm.add(jmi)
                    for mi2 in mi[3]:
                        jmi2 = JMenuItem(mi2[1])
                        jmi2.setActionCommand(mi2[0])
                        jmi2.setMnemonic(mi2[2])
                        jmi2.addActionListener(self)
                        self.menu[mi2[0]] = jmi2
                        jmi.add(jmi2)
                else:
                    jm.addSeparator()
            jmb.add(jm)
        self.setJMenuBar(jmb)

        root = DefaultMutableTreeNode(TreeNode(APP_NAME, 'ROOT'))
        for (name, params) in self.pref['TREE']:
            server = DefaultMutableTreeNode(TreeNode(name, 'SERVER'))
            for param in params:
                o = TreeNode(param.path, 'DATABASE')
                o.conn_param = param
                server.add(DefaultMutableTreeNode(o))
            root.add(server)

        self.tree = JTree(root)
        self.tree.setCellRenderer(JbTreeCellRenderer())
        self.tree.addTreeSelectionListener(self)
        self.tree.addMouseListener(TreeMouseListener(self))
        self.split = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, True, 
                            JScrollPane(self.tree), JScrollPane(JTable()))
        self.add(self.split)
        self.setLocation(Point(self.pref['X'], self.pref['Y']))
        self.setSize(Dimension(self.pref['WIDTH'], self.pref['HEIGHT']))
        self.split.setDividerLocation(self.pref['DIVIDER'])
        self.update_menu_tree(root)

    # Menu selection
    def actionPerformed(self, ae):
        ac = ae.getActionCommand()
        path = self.tree.getSelectionPath()
        if path:
            c = path.getLastPathComponent()
        else:
            c = self.tree.getModel().getRoot()
        node = c.getUserObject()
        if ac == 'REG_SERVER':
            s = JOptionPane.showInputDialog(self, "Server Name")
            if s != None:
                root = self.tree.getModel().getRoot()
                root.add(DefaultMutableTreeNode(TreeNode(s, 'SERVER')))
        elif ac == 'UNREG_SERVER':
            if c.getParent().getUserObject().node_type == 'ROOT':
                self.tree.getModel().removeNodeFromParent(c)
        elif ac == 'EDIT_SERVER':
            s = JOptionPane.showInputDialog(self, "Server Name", node)
            if s != None:
                node.name = s
        elif ac == 'REG_DB':
            dlg = ConnParamDialog(self)
            if dlg.conn_param:
                node = TreeNode(dlg.conn_param.path, 'DATABASE')
                node.conn_param = dlg.conn_param
                c.add(DefaultMutableTreeNode(node))
        elif ac == 'UNREG_DB':
            if c.getParent().getUserObject().node_type == 'SERVER':
                self.tree.getModel().removeNodeFromParent(c)
        elif ac == 'EDIT_DB':
            dlg = ConnParamDialog(self, node.conn_param)
            if dlg.conn_param:
                node.name = dlg.conn_param.path
                node.conn_param = dlg.conn_param
                c.setUserObject(node)
        elif ac == 'OPEN_DB':
            param = node.conn_param
            cancel = False
            if param.password == None:
                pwd = JPasswordField(10)
                if JOptionPane.showConfirmDialog(self, pwd,
                        "Enter %s's password" % (param.user), 
                        JOptionPane.YES_NO_OPTION) == JOptionPane.YES_OPTION:
                    param.password = String(pwd.getPassword())
                else:
                    cancel = True
            if not cancel:
                node.db = fbutil.FbDatabase(
                    host=c.getParent().getUserObject().name,
                    path=param.path, user=param.user, password=param.password,
                    charset=param.charset, port=param.port)
                try:
                    node.db.open()
                except Exception, e:
                    node.db = None
                    JOptionPane.showMessageDialog(self, str(e), 
                            "Can't Open Database", JOptionPane.ERROR_MESSAGE)
            self.update_menu_tree(c)
        elif ac == 'CLOSE_DB':
            node.db.close()
            node.db = None
            self.update_menu_tree(c)
        elif ac == 'ISQL':
            dlg = SqlDialog(self, node.db)
        elif ac == 'TABLE_CONSTRAINTS':
            h = ['NAME', 'CONDITION', 'TYPE', 'FIELDS']
            db = c.getParent().getParent().getUserObject().db
            d = []
            for row in db.constraints(node.name):
                r = []
                for k in h:
                    r.append(row[k])
                d.append(r)
            table = JTable(d, head_titles(h))
            loc = self.split.getDividerLocation()
            self.split.setRightComponent(JScrollPane(table))
            adjust_column_width(table)
            self.split.setDividerLocation(loc)
            table.setDefaultRenderer(Object, ShowConstraintsTableCellRenderer())
        elif ac == 'SHOW_INDEX':
            h = ['INDEX_NAME', 'CONST_NAME', 'CONST_TYPE', 'FOREIGN_KEY', 
                    'FIELD_NAME', 'UNIQUE_FLAG', 'UPDATE_RULE', 'DELETE_RULE', 
                    'STATISTICS', 'INACT']
            db = c.getParent().getParent().getUserObject().db
            d = []
            for row in db.key_constraints_and_index(node.name):
                r = []
                for k in h:
                    r.append(row[k])
                d.append(r)
            table = JTable(d, head_titles(h))
            loc = self.split.getDividerLocation()
            self.split.setRightComponent(JScrollPane(table))
            adjust_column_width(table)
            self.split.setDividerLocation(loc)
            table.setDefaultRenderer(Object, ShowIndexTableCellRenderer())
        elif ac == 'SHOW_REFERENCED_COLUMN':
            db = c.getParent().getParent().getUserObject().db
            h, d = db.referenced_columns(node.name)
            table = JTable(d, head_titles(h))
            loc = self.split.getDividerLocation()
            self.split.setRightComponent(JScrollPane(table))
            adjust_column_width(table)
            self.split.setDividerLocation(loc)
        elif ac == 'SHOW_GRANT':
            db = c.getParent().getParent().getUserObject().db
            priv = {'S' : 'SELECT', 
                'D' : 'DELETE', 
                'I' : 'INSERT', 
                'U' : 'UPDATE',
                'R' : 'REFERENCES',
                'X' : 'EXECUTE',
                }
            d = {}
            has_field_name = False
            h, rows = db.grant_users(node.name)
            for row in rows:
                r = dict(zip(h, row))
                d.setdefault((r['NAME'], r['GRANT_OPTION'], r['FIELD_NAME']),
                                            []).append(priv[r['PRIVILEGE']])
                if r['FIELD_NAME']:
                    has_field_name = True

            rh = ['NAME', 'PRIVIVILEGE', 'GRANT_OPTION']
            if has_field_name:
                rh.append('FIELD_NAME')
            rd = []
            for k in d:
                r = [k[0], ','.join(d[k]), k[1]]
                if has_field_name:
                    r.append(k[2])
                rd.append(r)
            table = JTable(rd, head_titles(rh))
            loc = self.split.getDividerLocation()
            self.split.setRightComponent(JScrollPane(table))
            adjust_column_width(table)
            self.split.setDividerLocation(loc)
        elif ac == 'VIEW_SOURCE':
            db = c.getParent().getParent().getUserObject().db
            if node.node_type == 'VIEW':
                sql = 'recreate view ' + node.name + ' as\n'
                sql += db.view_source(node.name)
            elif node.node_type == 'PROCEDURE':
                proc = db.procedure_source(node.name)
                sql = 'set term !! ;\n'
                sql += 'alter procedure ' + proc['NAME'] + '('
                sql += ','.join([in_p['NAME'] 
                            + ' ' + fbutil.fieldtype_to_string(in_p) 
                            for in_p in proc['IN_PARAMS']])
                sql += ')\nreturns ('
                sql += ','.join([out_p['NAME'] 
                            + ' ' + fbutil.fieldtype_to_string(out_p)
                            for out_p in proc['OUT_PARAMS']])
                sql += ') as\n' + '\n'.join(proc['SOURCE'].split('\n'))
                sql += '!!\nset term ; !!'
            text = JTextArea(sql)
            text.setEditable(False)
            loc = self.split.getDividerLocation()
            self.split.setRightComponent(JScrollPane(text))
            self.split.setDividerLocation(loc)
        elif ac == 'QUIT':
            self.quit_app(None)
        elif ac == 'ABOUT':
            s = [APP_NAME, ' ', __version__, '\n', 'Jython', sys.version]
            JOptionPane.showMessageDialog(self, 
                ''.join(s), 'Version', JOptionPane.INFORMATION_MESSAGE)

        self.tree.updateUI()

    # Tree selection
    def valueChanged(self, tse):
        path = self.tree.getSelectionPath()
        if not path:
            c = self.tree.getModel().getRoot()
        else:
            c = path.getLastPathComponent()
        node = c.getUserObject()
        fill_table = False
        fill_text = False
        try:
            db = c.getParent().getUserObject().db
        except:
            try:
                db = c.getParent().getParent().getUserObject().db
            except:
                pass

        if node.node_type == 'DOMAINS':
            h, d = db.domains()
            th = ['NAME', 'TYPE', 'CHECK', 'DEFAULT', 'DESCRIPTION']
            td = []
            for r in d:
                row = dict(zip(h, r))
                td.append([row['NAME'], fbutil.fieldtype_to_string(row, False),
                    row['VALIDATION_SOURCE'], fbutil.default_source_string(row),
                    row['DESCRIPTION']])
            h, d = th, td
            fill_table = True
        elif node.node_type == 'EXCEPTIONS':
            h, d = db.exceptions()
            fill_table = True
        elif node.node_type == 'FUNCTIONS':
            h, d = db.functions()
            fill_table = True
        elif node.node_type == 'GENERATORS':
            h, d = db.generators()
            h.append('COUNT')
            for r in d:
                r.append(db.get_generator_id(r[0]))
            fill_table = True
        elif node.node_type == 'PROCEDURES':
            h, d = db.procedures()
            if not c.getChildCount():
                for r in d:
                    c.add(DefaultMutableTreeNode(TreeNode(r[0], 'PROCEDURE')))
            fill_table = True
        elif node.node_type == 'PROCEDURE':
            h = ['NAME', 'I/O', 'TYPE', 'DESCRIPTION']
            d = []
            p = db.procedure_source(node.name)
            for in_p in p['IN_PARAMS']:
                d.append([in_p['NAME'], 'IN', 
                    fbutil.fieldtype_to_string(in_p), in_p['DESCRIPTION']])
            for out_p in p['OUT_PARAMS']:
                d.append([out_p['NAME'], 'OUT', 
                    fbutil.fieldtype_to_string(out_p), out_p['DESCRIPTION']])
            fill_table = True
        elif node.node_type == 'ROLES':
            h, d = db.roles()
            if not c.getChildCount():
                for r in d:
                    c.add(DefaultMutableTreeNode(TreeNode(r[0], 'ROLE')))
            fill_table = True
        elif node.node_type == 'ROLE':
            h, d = db.grant_users(node.name)
            fill_table = True
        elif node.node_type == 'TABLES' or node.node_type == 'SYSTEMTABLES':
            system_flag = 0 if node.node_type == 'TABLES' else 1
            h, d = db.tables(system_flag)
            if not c.getChildCount():
                for r in d:
                    k = 'TABLE' if node.node_type == 'TABLES' else 'SYSTEMTABLE'
                    c.add(DefaultMutableTreeNode(TreeNode(r[0], k)))
            fill_table = True
        elif node.node_type == 'TABLE' or node.node_type == 'SYSTEMTABLE':
            h, d = db.columns(node.name)
            th = ['NAME', 'TYPE', 'IS NULL', 'DEFAULT', 'DESCRIPTION']
            td = []
            for r in d:
                row = dict(zip(h, r))
                td.append([row['NAME'], fbutil.fieldtype_to_string(row),
                    row['NULL_FLAG'], row['DEFAULT_SOURCE'], 
                    row['DESCRIPTION']])
            h, d = th, td
            fill_table = True
        elif node.node_type == 'TRIGGERS':
            h, d = db.triggers()
            if not c.getChildCount():
                for r in d:
                    k = 'TRIGGER_INACT' if r[4] == '1' else 'TRIGGER'
                    c.add(DefaultMutableTreeNode(TreeNode(r[0], k)))
            fill_table = True
        elif node.node_type == 'TRIGGER' or node.node_type == 'TRIGGER_INACT':
            s = db.trigger_source(node.name)
            fill_text = True
        elif node.node_type == 'VIEWS':
            h, d = db.views()
            if not c.getChildCount():
                for r in d:
                    c.add(DefaultMutableTreeNode(TreeNode(r[0], 'VIEW')))
            fill_table = True
        elif node.node_type == 'VIEW':
            h, d = db.columns(node.name)
            fill_table = True
            th = ['NAME', 'TYPE', 'DESCRIPTION']
            td = []
            for r in d:
                row = dict(zip(h, r))
                td.append([row['NAME'], 
                        fbutil.fieldtype_to_string(row), row['DESCRIPTION']])
            h, d = th, td
            fill_table = True
        loc = self.split.getDividerLocation()
        if fill_table:
            table = JTable(d, head_titles(h))
            self.split.setRightComponent(JScrollPane(table))
            adjust_column_width(table)
        elif fill_text:
            text = JTextArea(s)
            text.setEditable(False)
            loc = self.split.getDividerLocation()
            self.split.setRightComponent(JScrollPane(text))
            self.split.setDividerLocation(loc)
        else:
            self.split.setRightComponent(JScrollPane())
        self.split.setDividerLocation(loc)

        if node.node_type == 'TABLE' or node.node_type == 'SYSTEMTABLE':
            pk = []
            fk = []
            uk = []
            for r in db.key_constraints_and_index(node.name):
                if r['CONST_TYPE'] == 'PRIMARY KEY':
                    pk += r['FIELD_NAME']
                elif r['CONST_TYPE'] == 'FOREIGN KEY':
                    fk += r['FIELD_NAME']
                elif r['CONST_TYPE'] == 'UNIQUE':
                    uk += r['FIELD_NAME']
            table.setDefaultRenderer(Object,
                    ColumnTableCellRenderer(pk, fk, uk))

        self.update_menu_tree(c)

class Application(Runnable):
    def run(self):
        jfrm = MainFrame()
        jfrm.visible = True


if __name__=="__main__":
    try:
        from java.net import ServerSocket
        sock = ServerSocket(21535)
    except:
        print(' '.join([APP_NAME, 'already running.']))
        sys.exit()
    SwingUtilities.invokeLater(Application())



