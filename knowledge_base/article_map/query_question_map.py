#!/usr/bin/env python3
"""Read-only classroom lookup. Default question view never returns mappings or answers."""
import argparse,json,re
from pathlib import Path

BASE=Path(__file__).resolve().parent

def read(name):
    return json.loads((BASE/name).read_text())

def matches_article(text, request):
    match=re.fullmatch(r'(?:GDPR\s*)?(\d+)',request,re.I)
    if not match:
        return bool(re.search(re.escape(request)+r'(?!\d)',text,re.I))
    wanted=int(match[1])
    for scope in re.findall(r'GDPR\s*([0-9(),\s–—\-]+)',text,re.I):
        scope=re.sub(r'\([^)]*\)','',scope)
        for lo,hi in re.findall(r'(\d+)(?:\s*[–—-]\s*(\d+))?',scope):
            if int(lo)<=wanted<=int(hi or lo):return True
    return False

def lookup(question=None,prepare=False,concept=None,article=None,section=None):
    qs=read('question_map.json')
    cs=read('concepts.json')
    if section:
        return read('textbook_sections.json').get(section,{'error':'小节不存在'})
    if question is not None:
        q=next((q for q in qs if q['q_no']==question),None)
        if q is None:return {'error':'题号不存在'}
        if not prepare:
            if q['answer_status']=='blocked_missing_question':
                return {'q_no':question,'error':'来源缺少明确设问，本题暂停课堂出题'}
            return {'q_no':question,'source_label':q['source_label'],'stem':q['source_stem'],'options':q['source_options']}
        book=read('textbook_sections.json')
        ids=list(dict.fromkeys(q['main_concepts']+q['associated_concepts']))
        return {
            'teacher_only':True,
            'protocol':(BASE/'教材优先与题库调用协议.md').read_text(),
            'question':q,
            'concepts':{i:cs[i] for i in ids},
            'textbook_actual_content':{sid:book[sid] for sid in q['textbook_sections']},
            'required_next_step':'读取正文并定位支持段落，区分教材原文、现行补充和事实适用；判分前核验唯一最佳答案。此数据包本身不生成正确答案。',
        }
    if article:
        # Numeral-only requests mean GDPR; do not confuse Art.3 with Art.30/38.
        ids={i for i,c in cs.items() if matches_article(c['article'],article)}
        hits=[]
        for q in qs:
            roles=[]
            if ids.intersection(q['main_concepts']):roles.append('main')
            for k,o in q['option_map'].items():
                if ids.intersection(o['concepts']) or matches_article(o['article_focus'],article):roles.append('option:'+k)
            if roles:hits.append({'q_no':q['q_no'],'task':q['task'],'roles':roles,'warning':q['warning']})
        return {'teacher_only':True,'article':article,'concepts':{i:cs[i] for i in sorted(ids)},'questions':hits,'note':'条文簇可能包含多个款项；请结合具体概念与option article_focus筛选。'}
    if concept:
        if concept not in cs:return {'error':'概念ID不存在'}
        return {'teacher_only':True,'concept':cs[concept],
            'main_questions':[q['q_no'] for q in qs if concept in q['main_concepts']],
            'option_only_questions':[q['q_no'] for q in qs if concept in q['associated_concepts']]}
    return read('manifest.json')

if __name__=='__main__':
    p=argparse.ArgumentParser()
    g=p.add_mutually_exclusive_group()
    g.add_argument('--question',type=int);g.add_argument('--concept');g.add_argument('--article');g.add_argument('--section')
    p.add_argument('--prepare',action='store_true')
    a=p.parse_args()
    if a.prepare and a.question is None:p.error('--prepare须同时指定--question')
    print(json.dumps(lookup(**vars(a)),ensure_ascii=False,indent=2))
