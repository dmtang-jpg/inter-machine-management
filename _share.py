import sys, urllib3
urllib3.disable_warnings()
sys.path.insert(0, '/home/dmt/workspace')
from tools.nju_box_api import NjuBox, BASE, REPO_ID

box = NjuBox()
box.login()

# 创建分享链接（JWT 认证即可，无需 CSRF；201 → Location header）
resp = box.session.put(
    f'{BASE}/api2/repos/{REPO_ID}/file/shared-link/',
    json={'p': '/耐高温磁性吸收剂_大项目申报模块.docx'},
    headers={
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    },
    timeout=20,
)
if resp.status_code == 201:
    print(f'LINK:{resp.headers.get("Location", "")}')
else:
    # 兜底：尝试创建（若已存在则从列表查）
    links = box.session.get(f'{BASE}/api/v2.1/share-links/', timeout=20)
    if links.status_code == 200:
        for lk in links.json():
            p = lk.get('path', '')
            if '大项目申报' in p:
                print(f'LINK:{lk["link"]}')
                break
        else:
            print('FAIL:', resp.status_code, resp.text[:300])
    else:
        print('FAIL:', resp.status_code, resp.text[:300])
