"""Apply signed team training releases without changing source criteria or budget."""
from copy import deepcopy


def comparable(option):
    return sorted([{'label': c['label'], 'expected': c['expected'], 'source_ids': sorted(c.get('source_ids', []))}
                   for c in option['criteria']], key=lambda c: (c['label'], c['expected'], c['source_ids']))


def apply_releases(sheet, releases, budget):
    from workflow import Problem
    if not releases:
        return
    if not isinstance(budget, int) or isinstance(budget, bool) or not 1 <= budget <= 20:
        raise Problem('共享策略需要预先确定 1—20 项准备预算')
    if sum(r['level'] == 'L3' for r in releases) > 1:
        raise Problem('一次准备只可选择一个已独立验证的选题策略，不能叠加未经验证的策略')
    priorities = sheet['priorities']
    blocks = {b['id'] for b in sheet['material']['blocks']}
    offers = []
    for r in releases:
        if r['lessonId'] != sheet['visit']['lesson_id'] or r['sourceRevision'] != sheet['material']['revision']:
            raise Problem('共享版本与当前课程资料不一致，请重新审核', 409)
        option = r['option']
        if not option.get('question') or not option.get('criteria') or any(not c.get('source_ids') or not set(c['source_ids']) <= blocks for c in option['criteria']):
            raise Problem('共享场景的原始资料引用无效', 409)
        matches = [p for p in priorities if comparable(p) == comparable(option)]
        if r['level'] == 'L2':
            if matches:
                continue  # No addition means no consumption claim.
            p = deepcopy(option)
            p.update(id='shared_' + r['id'].replace('-', ''), title='团队共享训练场景',
                     why='原任务场景经团队审核复用；请核对是否适合本次目标。',
                     fact_ids=[], skills=[c['id'] for c in option['criteria']], predicted=True,
                     shared_release={'id': r['id'], 'version': r['version']})
            priorities.append(p)
        elif r['level'] != 'L3':
            raise Problem('共享内容类型无效')
        offers.append(deepcopy(r))
    # Selection budget was supplied before generation. Too few candidates do not
    # justify silently changing that budget or inventing extra options.
    if budget > len(priorities):
        raise Problem('生成的候选少于已设预算，请降低预算重新生成', 409)
    baseline = [p['id'] for p in priorities[:budget]]
    proposed = baseline[:]
    applied = []
    for r in offers:
        if r['level'] != 'L3':
            continue
        matches = [p for p in priorities if comparable(p) == comparable(r['option'])]
        if len(matches) != 1:
            continue
        preferred = matches[0]['id']
        proposed = list(dict.fromkeys([preferred] + baseline + [p['id'] for p in priorities]))[:budget]
        if proposed != baseline:
            applied.append({'id': r['id'], 'version': r['version']})
    sheet['evolution'] = {'offers': offers, 'budget': budget, 'baseline': baseline, 'proposed': proposed,
                          'added': [x for x in proposed if x not in baseline],
                          'displaced': [x for x in baseline if x not in proposed], 'applied': applied,
                          'notice': '同一预算下的训练准备建议；是否使用由本人确认，不代表医生必问或医学审核。'}


def consumed(sheet, selected):
    records = [p['shared_release'] for p in sheet.get('priorities', [])
               if p['id'] in selected and p.get('shared_release')]
    e = sheet.get('evolution') or {}
    if set(selected) == set(e.get('proposed', [])):
        records += e.get('applied', [])
    return records
