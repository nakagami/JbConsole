##############################################################################
# Copyright (c) 2009, Hajime Nakagami<nakagami@da2.so-net.ne.jp>
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
from java.lang import *
from java.sql import *
from java.util import Properties
import org.firebirdsql.jdbc.FBDriver


def fieldtype_to_string(d, 
    resolve_typename = True, with_null_flag = False, with_default = False):
    if resolve_typename and d['FIELD_NAME'][:4] != 'RDB$':
        s = d['FIELD_NAME']     # DOMAIN's name
    else: # Builtin type
        if d['CHARACTER_LENGTH']:
            clen = str(d['CHARACTER_LENGTH'])
        else:
            clen = ''
        type_name = d['TYPE_NAME']
        if type_name == 'SHORT':
            s = 'SMALLINT'
        elif type_name == 'LONG':
            s = 'INTEGER'
        elif type_name == 'TEXT':
            s = 'CHAR(' + clen + ')'
        elif type_name == 'VARYING':
            s = 'VARCHAR(' + clen + ')'
        elif type_name == 'INT64':
            if d['FIELD_SUB_TYPE'] == 1:
                s = 'NUMERIC'
            else:
                s = 'DECIMAL('
            if d['FIELD_PRECISION']:
                s += d['FIELD_PRECISION']
                if d['FIELD_PRECISION'] and d['FIELD_SCALE']:
                    s += ','+str(int(d['FIELD_SCALE'])*-1)
            s += ')'
        elif type_name == 'BLOB':
            s = 'BLOB SUB_TYPE ' + str(d['FIELD_SUB_TYPE'])
        elif type_name == 'DOUBLE':
            s = 'DOUBLE PRECISION'
        else:
            s = type_name

    if with_default and d['DEFAULT_SOURCE']:
        s += ' ' + d['DEFAULT_SOURCE']
    if with_null_flag and d['NULL_FLAG'] == 1:
        s += ' NOT NULL'

    return s

def default_source_string(d):
    if d['DEFAULT_SOURCE'] != None:
        s =  str(d['DEFAULT_SOURCE'])
    elif d['DOM_DEFAULT_SOURCE'] != None: # DOMAIN
        s = str(d['DOM_DEFAULT_SOURCE']) + '(' + d['FIELD_NAME'].strip() + ')'
    else:
        s = ''
    return s

# Database connection wrapper
class FbDatabase(object):
    def __init__(self, host, path, user, password, charset='UNICODE_FSS', port=3050):
        self.host = host
        self.path = path
        self.user = user
        self.password = password
        self.port = port
        self.charset = charset
        self.conn = None

    def open(self):
        s = 'jdbc:firebirdsql:%s/%d:%s' % (self.host, self.port, self.path)
        props = Properties()
        props.setProperty("user", self.user)
        props.setProperty("password", self.password)
        props.setProperty("encoding", self.charset)
        self.conn = DriverManager.getConnection(s, props)
        return self.conn

    def close(self):
        self.conn.close()
        self.conn = None

    def execute(self, sqlStmt):
        cname = []
        result = []
        stmt = self.conn.createStatement()
        rs = stmt.executeQuery(sqlStmt)
        md = rs.getMetaData()
        num_column = md.getColumnCount()
        for i in range(1, num_column+1):
            cname.append(md.getColumnName(i))

        while rs.next():
            r = []
            for i in range(1, num_column+1):
                s = rs.getString(i)
                if s:
                    s = s.strip()
                r.append(s)
            result.append(r)

        rs.close()
        stmt.close()
        return (cname, result)

    def tables(self, system_flag=0):
        sqlStmt = '''select rdb$relation_name NAME,
            rdb$owner_name OWNER,
            rdb$description DESCRIPTION
            from rdb$relations 
            where rdb$system_flag=%d and rdb$view_source is null
            order by rdb$relation_name''' % system_flag
        return self.execute(sqlStmt)

    def views(self, name=None):
        sqlStmt = '''select rdb$relation_name NAME,
            rdb$owner_name OWNER,
            rdb$description DESCRIPTION
            from rdb$relations
            where rdb$flags=1 and rdb$view_source is not null
            order by rdb$relation_name'''
        return self.execute(sqlStmt)

    def view_source(self, name):
        sqlStmt = '''select rdb$view_source VIEW_SOURCE
            from rdb$relations
            where rdb$relation_name='%s' and 
                rdb$flags=1 and rdb$view_source is not null
            ''' % (name, )
        return self.execute(sqlStmt)[1][0][0]

    def roles(self):
        sqlStmt = '''select rdb$role_name NAME, rdb$owner_name OWNER
            from rdb$roles order by rdb$role_name'''
        return self.execute(sqlStmt)

    def grant_users(self, relation_name):
        sqlStmt = '''select rdb$user NAME, rdb$privilege PRIVILEGE,
            rdb$grant_option GRANT_OPTION, rdb$field_name FIELD_NAME
            from rdb$user_privileges where rdb$relation_name='%s'
            order by rdb$user ''' % (relation_name, )
        return self.execute(sqlStmt)

    def domains(self, dom_name=None):
        if dom_name:
            sqlStmt = '''select B.rdb$field_name NAME,
                C.rdb$type_name TYPE_NAME,
                B.rdb$field_sub_type FIELD_SUB_TYPE, 
                B.rdb$field_precision FIELD_PRECISION,
                B.rdb$field_scale FIELD_SCALE, 
                B.rdb$character_length "CHARACTER_LENGTH",
                B.rdb$field_name FIELD_NAME,
                B.rdb$validation_source VALIDATION_SOURCE,
                B.rdb$default_source DEFAULT_SOURCE,
                B.rdb$description DESCRIPTION
                from rdb$fields B, rdb$types C 
                where C.rdb$field_name='RDB$FIELD_TYPE'
                    and B.rdb$field_type=C.rdb$type
                    and B.rdb$field_name ='%s' ''' % (dom_name,)
        else:
            sqlStmt = '''select B.rdb$field_name NAME,
                C.rdb$type_name TYPE_NAME,
                B.rdb$field_sub_type FIELD_SUB_TYPE, 
                B.rdb$field_precision FIELD_PRECISION,
                B.rdb$field_scale FIELD_SCALE, 
                B.rdb$character_length "CHARACTER_LENGTH",
                B.rdb$field_name FIELD_NAME,
                B.rdb$validation_source VALIDATION_SOURCE,
                B.rdb$default_source DEFAULT_SOURCE,
                B.rdb$description DESCRIPTION
                from rdb$fields B, rdb$types C 
                where C.rdb$field_name='RDB$FIELD_TYPE'
                    and B.rdb$field_type=C.rdb$type
                    and not B.rdb$field_name like 'RDB$%'
                order by B.rdb$field_name'''
        return self.execute(sqlStmt)

    def exceptions(self):
        sqlStmt = '''select rdb$exception_name NAME,
            rdb$message MESSAGE_STRING, rdb$description DESCRIPTION
            from rdb$exceptions 
            order by rdb$exception_number'''
        return self.execute(sqlStmt)

    def columns(self, table_name):
        sqlStmt = '''select A.rdb$field_name NAME,
            A.rdb$null_flag NULL_FLAG, 
            A.rdb$default_source DEFAULT_SOURCE,
            A.rdb$description DESCRIPTION,
            C.rdb$type_name TYPE_NAME,
            B.rdb$field_sub_type FIELD_SUB_TYPE, 
            B.rdb$field_precision FIELD_PRECISION,
            B.rdb$field_scale FIELD_SCALE, 
            B.rdb$character_length "CHARACTER_LENGTH",
            B.rdb$field_name FIELD_NAME,
            B.rdb$default_source DOM_DEFAULT_SOURCE, 
            B.rdb$validation_source VALIDATION_SOURCE
            from rdb$relation_fields A, rdb$fields B, rdb$types C
            where C.rdb$field_name='RDB$FIELD_TYPE'
                and A.rdb$field_source = B.rdb$field_name
                and B.rdb$field_type=C.rdb$type 
                and  upper(A.rdb$relation_name) = '%s'
            order by A.rdb$field_position, A.rdb$field_name
            ''' % (table_name.upper(), )
        return self.execute(sqlStmt)
    
    def key_constraints_and_index(self, table_name):
        sqlStmt = '''select 
            A.rdb$index_name INDEX_NAME, 
            A.rdb$index_id INDEX_ID, 
            A.rdb$unique_flag UNIQUE_FLAG,
            A.rdb$index_inactive INACT,
            A.rdb$statistics STATISTIC,
            A.rdb$foreign_key FOREIGN_KEY, 
            B.rdb$field_name FIELD_NAME, 
            C.rdb$constraint_type CONST_TYPE, 
            C.rdb$constraint_name CONST_NAME,
            D.rdb$update_rule UPDATE_RULE, 
            D.rdb$delete_rule DELETE_RULE
            from rdb$indices A
                left join rdb$index_segments B
                        on A.rdb$index_name=B.rdb$index_name 
                left join rdb$relation_constraints C 
                        on A.rdb$index_name=C.rdb$index_name
                left join rdb$ref_constraints D 
                        on C.rdb$constraint_name=D.rdb$constraint_name
            where A.rdb$relation_name='%s' ''' % table_name
        head, rows = self.execute(sqlStmt)
    
        d = {}
        for r in rows:
            row = dict(zip(head, r))
            if not d.has_key(row['INDEX_ID']):
                d[row['INDEX_ID']] = {
                    'INDEX_NAME': row['INDEX_NAME'], 
                    'UNIQUE_FLAG': row['UNIQUE_FLAG'],
                    'INACT' : row['INACT'],
                    'STATISTICS' : row['STATISTIC'],
                    'CONST_TYPE': row['CONST_TYPE'], 
                    'CONST_NAME': row['CONST_NAME'],
                    'UPDATE_RULE': row['UPDATE_RULE'],
                    'DELETE_RULE': row['DELETE_RULE'],
                    'FIELD_NAME': [],
                }

                if row['FOREIGN_KEY']:
                    d[row['INDEX_ID']]['FOREIGN_KEY'] = \
                            self._references(row['FOREIGN_KEY'])
                else:
                    d[row['INDEX_ID']]['FOREIGN_KEY'] = ''
            d[row['INDEX_ID']]['FIELD_NAME'].append(row['FIELD_NAME'])
        # convert dict to array. Key value (INDEX_ID) is not need.
        a = []
        for k in d:
            a.append(d[k])
        return a
    
    def _references(self, index_name):
        sqlStmt = '''select 
            A.rdb$relation_name RELATION_NAME, 
            B.rdb$field_name FIELD_NAME 
            from rdb$indices A, rdb$index_segments B
            where A.rdb$index_name='%s' 
                and A.rdb$index_name=b.rdb$index_name''' % index_name
        h, d = self.execute(sqlStmt)
        return (index_name, d[0][0], [r[1] for r in d])  #index,table,[fields]
    
    def check_constraints(self, tabname):
        sqlStmt = '''select 
            A.rdb$constraint_name CHECK_NAME, 
            C.rdb$trigger_source CHECK_SOURCE 
            from rdb$relation_constraints A, rdb$check_constraints B, 
                rdb$triggers C
            where 
                A.rdb$constraint_type='CHECK' 
                and A.rdb$constraint_name = B.rdb$constraint_name 
                and B.rdb$trigger_name = C.rdb$trigger_name 
                and C.rdb$trigger_type=1
                and upper(A.rdb$relation_name) = '%s' ''' % tabname.upper()
        head, data = self.execute(sqlStmt)
        a = []
        for r in data:
            row = dict(zip(head, r))
            a.append({'CHECK_NAME': row['CHECK_NAME'],
                        'CHECK_SOURCE': row['CHECK_SOURCE']})
        return a

    def constraints(self, table_name):
        a = []
        key_constraints = self.key_constraints_and_index(table_name)
        for const_type in ('PRIMARY KEY', 'UNIQUE'):
            for r in key_constraints:
                if r['CONST_TYPE'] == const_type:
                    d = {}
                    d['NAME'] = r['CONST_NAME']
                    d['TYPE'] = r['CONST_TYPE']
                    d['FIELDS'] = ','.join(r['FIELD_NAME'])
                    d['CONDITION'] = ''
                    a.append(d)
        for r in key_constraints:
            if r['CONST_TYPE'] != 'FOREIGN KEY':
                continue
            d = {}
            d['TYPE'] = r['CONST_TYPE']
            d['NAME'] = r['CONST_NAME']
            d['FIELDS'] = ','.join(r['FIELD_NAME'])
            d['CONDITION'] = 'REFERENCES ' + r['FOREIGN_KEY'][1]
            d['CONDITION'] += '(' + ','.join(r['FOREIGN_KEY'][2]) + ')'
            if r['UPDATE_RULE'] != 'RESTRICT':
                d['CONDITION'] += ' ON UPDATE ' + r['UPDATE_RULE']
            if r['DELETE_RULE'] != 'RESTRICT':
                d['CONDITION'] += ' ON DELETE ' + r['DELETE_RULE']
            a.append(d)
            
        check_constraints = self.check_constraints(table_name)
        for r in check_constraints:
            d = {}
            d['TYPE'] = 'CHECK'
            d['NAME'] = r['CHECK_NAME']
            d['FIELDS'] = ''
            d['CONDITION'] = r['CHECK_SOURCE']
            a.append(d)

        return a

    def _keys(self, tname, key_type):
        sqlStmt = '''select 
            a.rdb$index_name INDEX_NAME, 
            b.rdb$field_name F
            from rdb$indices A
                left join rdb$index_segments B
                        on A.rdb$index_name=B.rdb$index_name 
                left join rdb$relation_constraints C 
                        on A.rdb$index_name=C.rdb$index_name
                left join rdb$ref_constraints D 
                        on C.rdb$constraint_name=D.rdb$constraint_name
            where upper(A.rdb$relation_name)='%s' 
                and c.rdb$constraint_type='%s' 
            ''' % (tname.upper(), key_type)
        return [r[1].strip() for r in self.execute(sqlStmt)[1]]

    def primary_keys(self, tname):
        return self._keys(tname, 'PRIMARY KEY')

    def unique_keys(self, tname):
        return self._keys(tname, 'UNIQUE')
    
    def foreign_keys(self, tname):
        sqlStmt = '''select
            A.rdb$index_name INDEX_NAME,
            A.rdb$foreign_key FOREING_KEY,
            B.rdb$field_name FIELD_NAME,
            C.rdb$constraint_type CONST_TYPE, 
            C.rdb$constraint_name CONST_NAME,
            D.rdb$update_rule UPDATE_RULE, 
            D.rdb$delete_rule DELETE_RULE,
            A2.rdb$relation_name REF_TABLE,
            B2.rdb$field_name REF_FIELD
            from rdb$indices A
                left join rdb$index_segments B
                        on A.rdb$index_name=B.rdb$index_name 
                left join rdb$relation_constraints C 
                        on A.rdb$index_name=C.rdb$index_name
                left join rdb$ref_constraints D 
                        on C.rdb$constraint_name=D.rdb$constraint_name
                ,
                rdb$indices A2, rdb$index_segments B2
            where upper(A.rdb$relation_name)='%s' 
                and A2.rdb$index_name=A.rdb$foreign_key
                and A2.rdb$index_name=B2.rdb$index_name
        ''' % tname.upper()
        return self.execute(sqlStmt)

    def referenced_columns(self, tname):
        sqlStmt = '''select 
            B2.rdb$field_name FIELD_NAME,
            C.rdb$constraint_name CONST_NAME,
            A.rdb$relation_name REFERENCED_TABLE, 
            B.rdb$field_name REFERENCED_FIELD
            from rdb$indices A
                left join rdb$relation_constraints C 
                        on A.rdb$index_name=C.rdb$index_name,
                rdb$index_segments B, 
                rdb$indices A2, rdb$index_segments B2
            where A.rdb$index_name=B.rdb$index_name
                and A2.rdb$index_name=B2.rdb$index_name
                and A.rdb$foreign_key = A2.rdb$index_name
                and A2.rdb$relation_name = '%s'
            ''' % tname.upper()
        return self.execute(sqlStmt)
    
    def generators(self):
        sqlStmt = '''select 
            rdb$generator_name NAME from rdb$generators 
            where rdb$system_flag is null or rdb$system_flag = 0 
            order by rdb$system_flag, rdb$generator_name'''
        r = []
        return self.execute(sqlStmt)

    def get_generator_id(self, gen_name):
        sqlStmt = 'select gen_id(' + gen_name + ', 0) V from rdb$database'
        (h, d) = self.execute(sqlStmt)
        return d[0][0]
    
    def triggers(self, tabname=None):
        if tabname:
            sqlStmt = '''select 
                rdb$trigger_name NAME, 
                rdb$relation_name TABLE_NAME,
                rdb$trigger_sequence SEQUENCE, 
                rdb$trigger_type TRIGGER_TYPE, 
                rdb$trigger_inactive INACT
                    from rdb$triggers
                    where (rdb$system_flag is null or rdb$system_flag = 0)
                        and rdb$relation_name='%s'
                    order by rdb$relation_name, rdb$trigger_type, 
                        rdb$trigger_sequence
            ''' % tabname
        else:
            sqlStmt = '''select 
                rdb$trigger_name NAME, 
                rdb$relation_name TABLE_NAME,
                rdb$trigger_sequence SEQUENCE, 
                rdb$trigger_type TRIGGER_TYPE, 
                rdb$trigger_inactive INACT
                    from rdb$triggers
                    where (rdb$system_flag is null or rdb$system_flag = 0)
                    order by rdb$relation_name, rdb$trigger_type,
                        rdb$trigger_sequence'''
        return self.execute(sqlStmt)

    def trigger_source(self, name):
        sqlStmt = '''select 
            rdb$relation_name TABLE_NAME,
            rdb$trigger_sequence SEQUENCE, 
            rdb$trigger_type TRIGGER_TYPE, 
            rdb$trigger_source SOURCE, 
            rdb$trigger_inactive INACT
                from rdb$triggers
                where rdb$trigger_name='%s' ''' % (name, )
        (h, d) = self.execute(sqlStmt)
        return 'recreate trigger ' + name + '\n' + d[0][3]

    def procedures(self):
        sqlStmt = '''select rdb$procedure_name NAME, 
            rdb$description DESCRIPTION
            from rdb$procedures order by rdb$procedure_name'''
        return self.execute(sqlStmt)

    def procedure_source(self, name):
        sqlStmt = '''select rdb$procedure_name NAME, 
                rdb$procedure_source SOURCE,
                rdb$description DESCRIPTION
            from rdb$procedures
            where rdb$procedure_name='%s' ''' % (name,)
        r = []
        head, procs = self.execute(sqlStmt)
        for row in procs:
            sqlStmt = '''select 
                A.rdb$parameter_name NAME, 
                A.rdb$description DESCRIPTION,
                C.rdb$type_name TYPE_NAME, 
                B.rdb$field_sub_type FIELD_SUB_TYPE, 
                B.rdb$field_precision FIELD_PRECISION,
                B.rdb$field_scale FIELD_SCALE, 
                B.rdb$character_length "CHARACTER_LENGTH",
                B.rdb$field_name FIELD_NAME,
                B.rdb$null_flag NULL_FLAG, B.rdb$default_source DEFAULT_SOURCE
                from rdb$procedure_parameters A, rdb$fields B, rdb$types C
                where C.rdb$field_name='RDB$FIELD_TYPE' 
                    and A.rdb$field_source = B.rdb$field_name 
                    and A.rdb$parameter_type = 0
                    and B.rdb$field_type=C.rdb$type 
                    and  A.rdb$procedure_name='%s'
                order by A.rdb$parameter_number''' % row[0]
            in_params = []
            head, params = self.execute(sqlStmt)
            for p in params:
                d = dict(zip(head, p))
                d['NAME'] = d['NAME'].strip()
                in_params.append(d)
            sqlStmt = ''' select 
                A.rdb$parameter_name NAME, 
                A.rdb$description DESCRIPTION,
                C.rdb$type_name TYPE_NAME,
                B.rdb$field_sub_type FIELD_SUB_TYPE, 
                B.rdb$field_precision FIELD_PRECISION,
                B.rdb$field_scale FIELD_SCALE, 
                B.rdb$character_length "CHARACTER_LENGTH",
                B.rdb$field_name FIELD_NAME,
                B.rdb$null_flag NULL_FLAG, B.rdb$default_source DEFAULT_SOURCE
                from rdb$procedure_parameters A, rdb$fields B, rdb$types C
                where C.rdb$field_name='RDB$FIELD_TYPE' 
                    and A.rdb$field_source = B.rdb$field_name 
                    and A.rdb$parameter_type = 1
                    and B.rdb$field_type=C.rdb$type 
                    and  A.rdb$procedure_name='%s'
                order by A.rdb$parameter_number''' % row[0]
            out_params = []
            head, params = self.execute(sqlStmt)
            for p in params:
                d = dict(zip(head, p))
                d['NAME'] = d['NAME'].strip()
                out_params.append(d)
            r.append({'NAME': row[0].strip(),
                    'SOURCE': row[1],
                    'DESCRIPTION': row[2],
                    'IN_PARAMS': in_params,
                    'OUT_PARAMS':out_params})
        return r[0] # only 1 record.

    def functions(self):
        sqlStmt = '''select rdb$function_name FUNCTION_NAME, 
            rdb$entrypoint ENTRYPOINT,
            rdb$module_name LIBNAME,
            rdb$description DESCRIPTION
            from rdb$functions 
            order by rdb$function_name
            '''
        return self.execute(sqlStmt)

#------------------------------------------------------------------------------
import sys, tempfile
if __name__ == '__main__':
    if len(sys.argv) == 2:
        testdir = sys.argv[1]
    else:
        testdir = tempfile.gettempdir()
        
    print 'testdir=' + testdir

    db = FbDatabase(host='localhost', path = testdir + '/test.fdb',
            user='sysdba', password='masterkey')
    db.open()

    print "\n[domains]"
    h, d = db.domains()
    print h
    for r in d:
        print r

    print "\n[exceptions]"
    h, d = db.exceptions()
    print h
    for r in d:
        print r

    print "\n[system tables]"
    h, d = db.tables(system_flag=1)
    print h
    for r in d:
        print r


    print "\n[tables]"
    th, ts = db.tables()
    print th
    for t in ts:
        print '\n', t
        h, cs = db.columns(t[0])
        print '\t', h
        print '\t',
        for c in cs:
            print '\t' + c[0] + ' ' + fieldtype_to_string(dict(zip(h, c))),
            print c[1], c[2] # owner, description
        print '\t[key_constraints_and_index:]\n',
        for kcs in db.key_constraints_and_index(t[0]):
            for k in kcs:
                print '\t'+k, kcs[k]
            print '\n'
                
        print '\t[check_constraints:]\n',
        for ccs in db.check_constraints(t[0]):
            for k in ccs:
                print '\t'+k, ccs[k]
        print '\n'

        print '\t[constraints:]\n',
        for cs in db.constraints(t[0]):
            print cs

        print '\t[primary_keys:]\n',
        for pk in db.primary_keys(t[0]):
            print pk

        print '\t[foreign_keys:]\n',
        for fk in db.foreign_keys(t[0]):
            print fk

        print '\t[unique_keys:]\n',
        for uk in db.unique_keys(t[0]):
            print uk

        print '\n  triggers:',
        h, cs = db.triggers(t[0])
        print h
        for c in cs:
            print c
            print db.trigger_source(c[0])

    print "\n[views]"
    vh, vs = db.views()
    print vh
    for v in vs:
        print v
        h, cs = db.columns(v[0])
        print '\t', h
        print '\t',
        for c in cs:
            print '\t' + c[0] + ' ' + fieldtype_to_string(dict(zip(h, c))),
            print c[1], c[2] # owner, description
        print db.view_source(v[0])

    print "\n[generators]"
    gh, gs = db.generators()
    for g in gs:
        print g,
        print db.get_generator_id(g[0])

    print "\n[procedure]"
    ph, ps = db.procedures()
    for p in ps:
        print p[0]
        q = db.procedure_source(p[0])
        print q['SOURCE']
        print "\n[in_params]"
        for inp in q['IN_PARAMS']:
            print inp['NAME'], fieldtype_to_string(inp)
        print "\n[out_params]"
        for outp in q['OUT_PARAMS']:
            print outp['NAME'], fieldtype_to_string(outp)

    print "\n[roles]"
    rh, rs = db.roles()
    for r in rs:
        print r[0] + ' ' + r[1]
        print "\t[grant_users]"
        uh, us = db.grant_users(r[0])
        print uh
        for u in us:
            print u

    print "\n[functions]"
    fh, fs = db.functions()
    print fh
    for f in fs:
        print f


