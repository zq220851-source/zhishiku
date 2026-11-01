// One fictional hackathon persona. Only hospital names are real institutions.
// Every coverage relationship, person, title and key-contact flag below is invented.
const HOSPITAL_SOURCE='https://hrss.suzhou.gov.cn/jsszhrss/gsbxsxcx/202605/23b01681549845fb94d81c9159cebeb5.shtml';
const doctors=(names,keyCount)=>names.map((name,index)=>({name,role:'肿瘤相关科室医生（演示）',key:index<keyCount}));

export const DEMO_PROFILE={
 id:'demo-me',name:'林知安',fictional:true,role:'高级医药代表',bu:'IO BU',territory:['姑苏区','虎丘区'],
 marketedProductIds:['1','2'],learningPipelineIds:['85'],
 hospitals:[
  {name:'苏州大学附属第一医院',district:'姑苏区',sourceUrl:HOSPITAL_SOURCE,doctors:doctors(['许闻溪','沈安澜','顾明舒','梁予宁'],3)},
  {name:'苏州市立医院',district:'姑苏区',sourceUrl:HOSPITAL_SOURCE,doctors:doctors(['周知远','唐一然','苏云棠'],2)},
  {name:'苏州平江医院',district:'姑苏区',sourceUrl:HOSPITAL_SOURCE,doctors:doctors(['陆可心','夏孟初','韩若川'],2)},
  {name:'苏州金阊医院',district:'姑苏区',sourceUrl:HOSPITAL_SOURCE,doctors:doctors(['何言之','丁嘉禾','孟书宁'],2)},
  {name:'苏州科技城医院',district:'虎丘区',sourceUrl:HOSPITAL_SOURCE,doctors:doctors(['徐遥','袁真','邵景行','白雨晴'],2)},
  {name:'苏州高新区人民医院',district:'虎丘区',sourceUrl:HOSPITAL_SOURCE,doctors:doctors(['郑知微','蒋望舒','程云舟'],2)},
  {name:'苏州明基医院',district:'虎丘区',sourceUrl:HOSPITAL_SOURCE,doctors:doctors(['林沐言','叶同'],1)}
 ]
};

const WORK_CENTER={
 title:'肿瘤免疫 · 结肠癌新辅助治疗',
 detail:'达伯舒®（信迪利单抗，PD-1）＋达伯欣®（伊匹木单抗N01，CTLA-4）。已批准的联合适应证限定于可手术切除的 IIB–III 期 MSI-H/dMMR 结肠癌新辅助治疗；其他疾病场景须分别核对批准范围。',
 sourceUrl:'https://www1.hkexnews.hk/listedco/listconews/sehk/2025/1229/2025122900105_c.pdf',
 focus:[
  {id:'colon',name:'结肠癌与 MSI-H/dMMR',terms:['结肠癌','结直肠癌','肠癌','colon cancer','colorectal','msi-h','dmmr','mismatch repair','微卫星','错配修复']},
  {id:'immunity',name:'肿瘤免疫与 PD-1',terms:['免疫治疗','肿瘤免疫','pd-1','pd1','immunotherap','checkpoint inhibitor','信迪利单抗','sintilimab']},
  {id:'ctla4',name:'CTLA-4 与双免联合',terms:['ctla-4','ctla4','双免','伊匹木单抗','ipilimumab','ibi310']}
 ]
};
const PUBLIC_DOCTOR_EXAMPLE={name:'陶敏',hospital:'苏州大学附属第一医院',role:'肿瘤科公开学术案例',relationship:'公开资料中的学术方向案例；不是演示员工的真实客户或分配医生。',sourceUrl:'https://www.csco.org.cn/cn/ncontent.aspx?oid=9192'};

export function demoProfileSummary(products){
 const marketed=DEMO_PROFILE.marketedProductIds.map(id=>products.find(p=>p.id===id&&p.status==='marketed')).filter(Boolean);
 const learning=DEMO_PROFILE.learningPipelineIds.map(id=>products.find(p=>p.id===id&&p.status==='investigational')).filter(Boolean);
 const hospitals=DEMO_PROFILE.hospitals.map(({name,district,sourceUrl,doctors})=>({name,district,sourceUrl,doctorCount:doctors.length,keyCount:doctors.filter(d=>d.key).length,doctors}));
 return {id:DEMO_PROFILE.id,name:DEMO_PROFILE.name,fictional:true,role:DEMO_PROFILE.role,bu:DEMO_PROFILE.bu,territory:DEMO_PROFILE.territory,
  productIds:marketed.map(p=>p.id),marketed:marketed.map(({id,name,generic,target,sourceUrl})=>({id,name,generic:generic?.replace(/N\d+$/,'')||null,target,sourceUrl})),
  learning:learning.map(({id,name,target,sourceUrl})=>({id,name,target:id==='85'?'PD-1 / IL-2（α 偏向性）双特异性融合蛋白':target,sourceUrl,status:'在研学习 · 尚未获批'})),
  hospitals,hospitalCount:hospitals.length,doctorCount:hospitals.reduce((n,h)=>n+h.doctorCount,0),keyCount:hospitals.reduce((n,h)=>n+h.keyCount,0),workCenter:WORK_CENTER,publicDoctorExample:PUBLIC_DOCTOR_EXAMPLE,
  note:'仅用于黑客松演示。岗位与数量参照用户提供的示例截图；人物、医院覆盖关系和个人管线分配均为虚构。医院名称来自苏州市公开机构名录，医生与关键人不对应真实人员。'};
}
