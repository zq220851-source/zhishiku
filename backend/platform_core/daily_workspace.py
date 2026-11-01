"""Full read-only source access plus employee-owned working context, never demo identities."""
import hashlib
import json
import os
from urllib.parse import urlencode
import httpx
from fastapi import Depends, HTTPException
from sqlalchemy import select, insert, update
from .db import states
from .security import now
from pydantic import BaseModel

class ArticleBody(BaseModel):
    article: dict



def fetch_daily(path):
    base=os.environ.get('MEDREP_DAILY_WORKSPACE_ORIGIN','http://127.0.0.1:8887')
    if base not in ('http://127.0.0.1:8787','http://127.0.0.1:8887'):raise HTTPException(503,'日报内部地址无效')
    try:
        with httpx.Client(timeout=100,follow_redirects=False,trust_env=False) as client:
            with client.stream('GET',base+path) as response:
                raw=bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw)>8_000_000:raise HTTPException(502,'日报响应过大')
                data=json.loads(raw)
                if response.status_code>=400:raise HTTPException(response.status_code,str(data.get('error','日报读取失败'))[:180])
                if not isinstance(data,dict):raise ValueError()
                return data
    except HTTPException:raise
    except (ValueError,httpx.HTTPError):raise HTTPException(503,'日报服务不可用，请检查服务和来源连接')


def attach_daily_workspace(app,actor,engine):
    def profile(user):
        with engine.connect() as conn:
            row=conn.execute(select(states).where(states.c.user_id==user['id'],states.c.module=='daily',states.c.state_key=='work_profile')).mappings().first()
        value=json.loads(row['json_value']) if row else {}
        return value if isinstance(value,dict) else {}

    def article_key(id):
        if not isinstance(id,str) or not 1<=len(id)<=512:
            raise HTTPException(422,'文章标识无效')
        return 'article_'+hashlib.sha256(id.encode()).hexdigest()

    @app.get('/v1/mobile/daily/article')
    def read_article(id:str,user=Depends(actor)):
        key=article_key(id)
        with engine.connect() as conn:
            row=conn.execute(select(states.c.json_value).where(states.c.user_id==user['id'],states.c.module=='daily',states.c.state_key==key)).scalar_one_or_none()
        if row is None:raise HTTPException(404,'尚未保存此条目的完整内容，请从日报或检索结果重新打开')
        return {'article':json.loads(row)}

    @app.post('/v1/mobile/daily/article')
    def save_article(body:ArticleBody,user=Depends(actor)):
        key=article_key(body.article.get('id'))
        content=json.dumps(body.article,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        if len(content.encode())>60000:raise HTTPException(413,'单篇资料超出保存上限，未截断内容；请保留原始来源')
        with engine.begin() as conn:
            row=conn.execute(select(states.c.revision).where(states.c.user_id==user['id'],states.c.module=='daily',states.c.state_key==key)).scalar_one_or_none()
            if row is None:
                conn.execute(insert(states).values(user_id=user['id'],module='daily',state_key=key,json_value=content,revision=1,updated_at=now()))
            else:
                conn.execute(update(states).where(states.c.user_id==user['id'],states.c.module=='daily',states.c.state_key==key).values(json_value=content,revision=row+1,updated_at=now()))
        return {'saved':True,'id':body.article['id']}

    @app.get('/v1/mobile/daily/config')
    def config(_user=Depends(actor)):
        data=fetch_daily('/api/config')
        # Product choices are source data, no fabricated representative assignment.
        return {k:data.get(k) for k in ('products','pipeline','topics','sources','translation','scheduleEnabled','timeZone','notice')}

    @app.get('/v1/mobile/daily/workspace')
    def digest(length:str='standard',user=Depends(actor)):
        if length not in ('brief','standard'):raise HTTPException(422,'阅读长度无效')
        p=profile(user)
        def identifiers(key):
            values=p.get(key,[])
            if not isinstance(values,list) or len(values)>50 or any(not isinstance(x,str) or len(x)>80 for x in values):raise HTTPException(422,'请重新保存工作方向')
            return ','.join(values)
        data=fetch_daily('/api/digest?'+urlencode({'mode':'live','length':length,'products':identifiers('productIds'),'pipeline':identifiers('pipelineIds'),'topics':identifiers('topicIds')}))
        # Feed includes full source metadata/abstracts; do not discard learning.
        return {**data,'employee_context':{'display_name':user['display_name'],'source':'SELF_REPORTED_WORK_PROFILE','bu':str(p.get('bu',''))[:100]}}

    @app.get('/v1/mobile/daily/scholar')
    def scholar(hospital:str,name:str,_user=Depends(actor)):
        if not 3<=len(hospital)<=80 or not 2<=len(name)<=30:raise HTTPException(422,'请输入完整医院和姓名')
        return fetch_daily('/api/scholar-profile?'+urlencode({'hospital':hospital,'name':name}))

    @app.get('/v1/mobile/daily/translation')
    def translation(id:str,_user=Depends(actor)):
        if not 1<=len(id)<=512:raise HTTPException(422,'文章标识无效')
        return fetch_daily('/api/translation?'+urlencode({'id':id}))

    @app.get('/v1/mobile/daily/delivery-preview')
    def preview(user=Depends(actor)):
        d=digest('brief',user)
        sections=[f"{user['display_name']}的日报 · {d.get('date','')}"]
        for name,key in [('行业动态','industry'),('产品与在研学习','learning')]:
            sections.append(name)
            for item in d.get(key,[]):sections.append(f"{item.get('title','')}\n{item.get('summary','')}\n{item.get('url','')}")
        return {'status':'preview_only','channel':'feishu','message':'\n\n'.join(sections),'notice':'仅生成预览；没有向任何人发送。'}
