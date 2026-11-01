import test from 'node:test';
import assert from 'node:assert/strict';
import {parseCscoAgenda,reviewedPublicEvents} from '../src/conference.mjs';

const agenda=`<span>2026-09-17 下午</span><b>非小细胞肺癌专场1-免疫治疗专场</b><table>
<tr><td rowspan=2>16:35-17:00</td><td></td><td><p>专家讨论</p></td><td>陶敏</td><td>苏州大学附属第一医院</td></tr>
<tr><td>陶敏</td><td>其他医院</td></tr>
<tr><td>17:05-17:15</td><td>口头报告</td><td>结直肠癌免疫研究</td><td>李伟</td><td>苏州大学附属第一医院</td></tr></table>`;

test('官方会议日程仅收录姓名、医院和角色在同一行的记录',()=>{
 const tao=parseCscoAgenda(agenda,'陶敏','苏州大学附属第一医院');
 assert.equal(tao.length,1);assert.equal(tao[0].role,'专家讨论');assert.equal(tao[0].kind,'会议');
 assert.match(tao[0].title,/非小细胞肺癌专场/);assert.equal(tao[0].date,'2026-09-17');
 assert.deepEqual(parseCscoAgenda(agenda,'陶敏','其他医院'),[]);
 const li=parseCscoAgenda(agenda,'李伟','苏州大学附属第一医院');
 assert.equal(li.length,1);assert.equal(li[0].kind,'演讲');
});

test('人工核对的历史案例只用于指定医生和医院，且区分会议与讲座',()=>{
 const cases=reviewedPublicEvents('陶敏','苏州大学附属第一医院');
 assert.equal(cases.length,2);assert.deepEqual(cases.map(x=>x.kind),['会议','演讲']);
 assert.deepEqual(reviewedPublicEvents('陶敏','其他医院'),[]);
 assert.match(cases[1].snippet,/历史记录/);
});
