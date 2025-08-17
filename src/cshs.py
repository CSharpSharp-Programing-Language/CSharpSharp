#!/usr/bin/env python3
# C## interpreter/CLI
# Features: vars, functions, if/else, while, for, foreach, List(), Console.WriteLine/ReadLine, indexing.
import sys, re, argparse, json

# ---------- Lexer ----------
TOKEN_SPEC = [
    ('NUMBER',   r'\d+(?:\.\d+)?'),
    ('STRING',   r'"(?:\\.|[^"\\])*"'),
    ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),
    ('OP',       r'==|!=|<=|>=|&&|\|\||[+\-*/%<>=!.,;:{}()[\]]'),
    ('WS',       r'[ \t\r\n]+'),
    ('COMMENT',  r'//[^\n]*'),
]
MASTER = re.compile('|'.join('(?P<%s>%s)' % p for p in TOKEN_SPEC))

KEYWORDS = {
    'if','else','while','for','foreach','in','return','namespace','using',
    'var','int','float','string','bool','List',
    'true','false'
}

class Token:
    def __init__(self, typ, val, pos):
        self.type=typ; self.val=val; self.pos=pos
    def __repr__(self): return f'Token({self.type},{self.val})'

def lex(src):
    out=[]
    for m in MASTER.finditer(src):
        k=m.lastgroup; v=m.group()
        if k in ('WS','COMMENT'): continue
        if k=='ID' and v in KEYWORDS: k=v.upper()
        out.append(Token(k,v,m.start()))
    out.append(Token('EOF','',len(src)))
    return out

# ---------- Parser helpers ----------
class ParseError(Exception): pass
class Parser:
    def __init__(self,toks):
        self.toks=toks; self.i=0
    def peek(self): return self.toks[self.i]
    def eat(self,typ=None,val=None):
        t=self.peek()
        if typ and t.type!=typ: raise ParseError(f'Expected {typ}, got {t.type} at {t.pos}')
        if val and t.val!=val: raise ParseError(f'Expected {val}, got {t.val} at {t.pos}')
        self.i+=1; return t
    def match(self,typ,val=None):
        t=self.peek()
        if t.type==typ and (val is None or t.val==val):
            self.i+=1; return True
        return False

# AST nodes (as dicts)
def node(kind, **kw): d={'kind':kind}; d.update(kw); return d

# ---------- Expression parsing (Pratt) ----------
PRECEDENCE = {
    '||':1, '&&':2, '==':3, '!=':3, '<':4,'>':4,'<=':4,'>=':4,
    '+':5,'-':5,'*':6,'/':6,'%':6,
}
UNARY_OPS = {'-','!','+'}

def parse_expression(p):
    def parse_primary():
        t=p.peek()
        if t.type=='NUMBER':
            p.eat(); return node('number', value=float(t.val) if '.' in t.val else int(t.val))
        if t.type=='STRING':
            p.eat(); return node('string', value=bytes(t.val[1:-1],'utf-8').decode('unicode_escape'))
        if t.type in ('TRUE','FALSE'):
            p.eat(); return node('bool', value=(t.type=='TRUE'))
        if t.type=='ID' or t.type in ('CONSOLE','LIST'):
            parts=[p.eat().val]
            while p.match('OP','.'): parts.append(p.eat('ID').val)
            if p.match('OP','('):
                args=[]
                if not p.match('OP',')'):
                    while True:
                        args.append(parse_expression())
                        if p.match('OP',')'): break
                        p.eat('OP',',')
                return node('call', callee='.'.join(parts), args=args)
            if p.match('OP','['):
                idx=parse_expression(); p.eat('OP',']')
                return node('index', target='.'.join(parts), index=idx)
            return node('var', name='.'.join(parts))
        if p.match('OP','('):
            e=parse_expression(); p.eat('OP',')'); return e
        if t.type=='OP' and t.val in UNARY_OPS:
            op=p.eat('OP').val; expr=parse_expression()
            return node('unary', op=op, expr=expr)
        raise ParseError(f'Unexpected token {t}')
    def parse_binop(minp, left):
        while True:
            t=p.peek()
            if t.type!='OP' or t.val not in PRECEDENCE: break
            prec=PRECEDENCE[t.val]
            if prec<minp: break
            op=p.eat('OP').val
            right=parse_unary()
            t2=p.peek()
            while t2.type=='OP' and t2.val in PRECEDENCE and PRECEDENCE[t2.val]>prec:
                right=parse_binop(PRECEDENCE[t2.val], right); t2=p.peek()
            left=node('bin', op=op, left=left, right=right)
        return left
    def parse_unary():
        t=p.peek()
        if t.type=='OP' and t.val in UNARY_OPS:
            op=p.eat('OP').val
            expr=parse_unary()
            return node('unary', op=op, expr=expr)
        return parse_primary()
    left=parse_unary()
    return parse_binop(1,left)

# ---------- Statements ----------
def parse_block(p):
    p.eat('OP','{')
    items=[]
    while not p.match('OP','}'):
        items.append(parse_statement(p))
    return node('block', body=items)

def parse_var_decl(p):
    typ='var'
    if p.match('VAR'): typ='var'
    elif p.peek().type in ('INT','FLOAT','STRING','BOOL','LIST','ID'):
        typ=p.eat().val
        if typ=='List' and p.match('OP','<'):
            while not p.match('OP','>'): p.eat()
    name=p.eat('ID').val
    init=None
    if p.match('OP','='): init=parse_expression(p)
    p.eat('OP',';')
    return node('vardecl', type=typ, name=name, init=init)

def parse_for(p):
    p.eat('FOR'); p.eat('OP','(')
    init=None; cond=None; post=None
    if not p.match('OP',';'):
        if p.peek().type in ('VAR','INT','FLOAT','STRING','BOOL','LIST','ID') and p.toks[p.i+1].type=='ID':
            init=parse_var_decl(p)
        else:
            init=parse_expression(p); p.eat('OP',';')
    if not p.match('OP',';'):
        cond=parse_expression(p); p.eat('OP',';')
    if not p.match('OP',')'):
        post=parse_expression(p); p.eat('OP',')')
    body=parse_statement(p)
    return node('for', init=init, cond=cond, post=post, body=body)

def parse_foreach(p):
    p.eat('FOREACH'); p.eat('OP','(')
    if p.peek().type in ('VAR','INT','FLOAT','STRING','BOOL','LIST','ID'): p.eat()
    name=p.eat('ID').val
    p.eat('IN')
    seq=p.eat('ID').val
    p.eat('OP',')')
    body=parse_statement(p)
    return node('foreach', name=name, seq=seq, body=body)

def parse_if(p):
    p.eat('IF'); p.eat('OP','(')
    cond=parse_expression(p); p.eat('OP',')')
    then=parse_statement(p)
    otherwise=None
    if p.match('ELSE'): otherwise=parse_statement(p)
    return node('if', cond=cond, then=then, otherwise=otherwise)

def parse_stmt_or_expr(p):
    e=parse_expression(p)
    if isinstance(e,dict) and e['kind'] in ('var','index') and p.match('OP','='):
        val=parse_expression(p); p.eat('OP',';')
        return node('assign', target=e, value=val)
    p.eat('OP',';')
    return node('expr', expr=e)

def parse_function(p):
    rettype='void'
    if p.peek().type in ('INT','FLOAT','STRING','BOOL','ID','VAR','LIST'): rettype=p.eat().val
    name=p.eat('ID').val
    p.eat('OP','(')
    params=[]
    if not p.match('OP',')'):
        while True:
            if p.peek().type in ('INT','FLOAT','STRING','BOOL','ID','VAR','LIST'): p.eat()
            pid=p.eat('ID').val; params.append(pid)
            if p.match('OP',')'): break
            p.eat('OP',',')
    body=parse_block(p)
    return node('func', name=name, params=params, body=body, rettype=rettype)

def parse_statement(p):
    t=p.peek()
    if t.type=='OP' and t.val=='{': return parse_block(p)
    if t.type=='IF': return parse_if(p)
    if t.type=='WHILE':
        p.eat('WHILE'); p.eat('OP','('); cond=parse_expression(p); p.eat('OP',')'); body=parse_statement(p)
        return node('while', cond=cond, body=body)
    if t.type=='FOR': return parse_for(p)
    if t.type=='FOREACH': return parse_foreach(p)
    if t.type=='RETURN':
        p.eat('RETURN')
        if p.peek().type=='OP' and p.peek().val==';':
            p.eat('OP',';'); return node('return', value=None)
        val=parse_expression(p); p.eat('OP',';'); return node('return', value=val)
    if t.type in ('VAR','INT','FLOAT','STRING','BOOL','LIST','ID'):
        j=p.i
        try:
            tok1=p.toks[j]; tok2=p.toks[j+1]; tok3=p.toks[j+2]
            if tok2.type=='ID' and tok3.type=='OP' and tok3.val=='(':
                return parse_function(p)
        except Exception: pass
        if t.type in ('VAR','INT','FLOAT','STRING','BOOL','LIST','ID') and p.toks[p.i+1].type=='ID':
            return parse_var_decl(p)
        return parse_stmt_or_expr(p)
    return parse_stmt_or_expr(p)

def parse_program(src):
    toks=lex(src); p=Parser(toks); items=[]
    while p.peek().type!='EOF':
        if p.peek().type=='USING':
            p.eat('USING'); p.eat('ID')
            while p.match('OP','.'): p.eat('ID')
            p.eat('OP',';'); continue
        if p.peek().type=='NAMESPACE':
            p.eat('NAMESPACE'); p.eat('ID'); items.append(parse_block(p)); continue
        items.append(parse_statement(p))
    return node('program', body=items)

# ---------- Interpreter ----------
class ReturnSignal(Exception):
    def __init__(self, value): self.value=value

class Runtime:
    def __init__(self):
        self.globals={}
        self.functions={}
        self.stdlib=self.load_stdlib()

    def load_stdlib(self):
        class ConsoleNS: pass
        Console=ConsoleNS()
        def WriteLine(*args): print(*args)
        def ReadLine(): 
            try: return input()
            except EOFError: return ""
        Console.WriteLine=WriteLine; Console.ReadLine=ReadLine
        class CSList(list):
            def push_back(self,x): self.append(x)
            def add(self,x): self.append(x)
            def size(self): return len(self)
        def List_ctor(): return CSList()
        return {'Console':Console, 'List':List_ctor}

    def eval_expr(self, env, e):
        k=e['kind']
        if k in ('number','string','bool'): return e['value']
        if k=='var':
            name=e['name']
            if name in env: return env[name]
            if name in self.globals: return self.globals[name]
            if '.' in name:
                parts=name.split('.')
                obj=self.stdlib.get(parts[0], None)
                if obj is None: raise NameError(name)
                for part in parts[1:]: obj=getattr(obj, part)
                return obj
            if name in self.stdlib: return self.stdlib[name]
            raise NameError(name)
        if k=='call':
            callee=e['callee']
            if '.' in callee:
                parts=callee.split('.')
                if parts[0]=='Console':
                    fn=getattr(self.stdlib['Console'], parts[1])
                    args=[self.eval_expr(env,a) for a in e['args']]
                    return fn(*args)
            if callee=='List': return self.stdlib['List']()
            if callee in self.functions:
                f=self.functions[callee]
                args=[self.eval_expr(env,a) for a in e['args']]
                new_env=dict(self.globals)
                for name,val in zip(f['params'], args): new_env[name]=val
                try:
                    self.exec_block(new_env, f['body'])
                except ReturnSignal as r:
                    return r.value
                return None
            if callee in env and callable(env[callee]):
                return env[callee](*[self.eval_expr(env,a) for a in e['args']])
            raise NameError(callee)
        if k=='index':
            tgt=self.eval_expr(env, node('var', name=e['target']))
            idx=self.eval_expr(env, e['index'])
            return tgt[idx]
        if k=='unary':
            v=self.eval_expr(env,e['expr']); op=e['op']
            return {'-':lambda x:-x, '!':lambda x:not x, '+':lambda x:+x}[op](v)
        if k=='bin':
            l=self.eval_expr(env,e['left']); r=self.eval_expr(env,e['right']); op=e['op']
            ops={'+':lambda a,b:a+b, '-':lambda a,b:a-b, '*':lambda a,b:a*b, '/':lambda a,b:a/b, '%':lambda a,b:a%b,
                 '==':lambda a,b:a==b, '!=':lambda a,b:a!=b, '<':lambda a,b:a<b, '>':lambda a,b:a>b, '<=':lambda a,b:a<=b, '>=':lambda a,b:a>=b,
                 '&&':lambda a,b:bool(a) and bool(b), '||':lambda a,b:bool(a) or bool(b)}
            return ops[op](l,r)
        raise RuntimeError(f'unknown expr {k}')

    def exec_block(self, env, block):
        for stmt in block['body']:
            self.exec_stmt(env, stmt)

    def exec_stmt(self, env, s):
        k=s['kind']
        if k=='block': self.exec_block(env, s); return
        if k=='vardecl':
            val=self.eval_expr(env, s['init']) if s['init'] else None
            env[s['name']]=val; return
        if k=='assign':
            tgt=s['target']
            if tgt['kind']=='var':
                name=tgt['name']
                if name in env: env[name]=self.eval_expr(env, s['value'])
                elif name in self.globals: self.globals[name]=self.eval_expr(env, s['value'])
                else: env[name]=self.eval_expr(env, s['value'])
                return
            if tgt['kind']=='index':
                arr=self.eval_expr(env, node('var', name=tgt['target']))
                idx=self.eval_expr(env, tgt['index'])
                arr[idx]=self.eval_expr(env, s['value']); return
        if k=='expr': self.eval_expr(env, s['expr']); return
        if k=='if':
            if self.eval_expr(env, s['cond']): self.exec_stmt(env, s['then'])
            elif s['otherwise'] is not None: self.exec_stmt(env, s['otherwise'])
            return
        if k=='while':
            while self.eval_expr(env, s['cond']): self.exec_stmt(env, s['body'])
            return
        if k=='for':
            if s['init']:
                if s['init']['kind']=='vardecl': self.exec_stmt(env, s['init'])
                else: self.eval_expr(env, s['init']['expr'] if s['init']['kind']=='expr' else s['init'])
            while True:
                cond=True if s['cond'] is None else self.eval_expr(env, s['cond'])
                if not cond: break
                self.exec_stmt(env, s['body'])
                if s['post']: self.eval_expr(env, s['post'])
            return
        if k=='foreach':
            seq=env.get(s['seq'], self.globals.get(s['seq']))
            for val in seq:
                env[s['name']]=val; self.exec_stmt(env, s['body'])
            return
        if k=='return':
            val=self.eval_expr(env, s['value']) if s['value'] is not None else None
            raise ReturnSignal(val)
        if k=='func': self.functions[s['name']]=s; return
        raise RuntimeError(f'unknown stmt {k}')

def run_source(src):
    prog=parse_program(src); rt=Runtime(); env=rt.globals
    for item in prog['body']:
        if item['kind']=='func': rt.exec_stmt(env, item)
    for item in prog['body']:
        if item['kind']!='func': rt.exec_stmt(env, item)
    if 'Main' in rt.functions:
        try: rt.exec_stmt(env, node('expr', expr=node('call','Main',[])))
        except ReturnSignal as r: return r.value
    return None

def main():
    ap=argparse.ArgumentParser(description='C## interpreter')
    sub=ap.add_subparsers(dest='cmd', required=True)
    r=sub.add_parser('run'); r.add_argument('file')
    a=sub.add_parser('ast'); a.add_argument('file')
    replp=sub.add_parser('repl')
    args=ap.parse_args()
    if args.cmd=='run':
        with open(args.file,'r',encoding='utf-8') as f: src=f.read()
        run_source(src)
    elif args.cmd=='ast':
        with open(args.file,'r',encoding='utf-8') as f: src=f.read()
        print(json.dumps(parse_program(src), indent=2))
    elif args.cmd=='repl':
        print('C## REPL. End with Ctrl-D.')
        buf=''
        try:
            while True:
                line=input('>>> ')
                buf+=line+'\n'
                if line.strip().endswith(';') or line.strip().endswith('}'):
                    try: run_source(buf)
                    except Exception as e: print('Error:', e)
                    buf=''
        except EOFError: pass

if __name__=='__main__': main()
