# DEV_NOTES

## 실제 사용 파일
- app.py
- setflow/db.py
- setflow/models.py
- setflow/init_db.py
- templates/base.html
- templates/login.html
- templates/or_use.html
- templates/csr.html
- templates/admin.html
- static/styles.css
- static/app.js

## 주의점
- csr.html에서 groups 구조를 크게 바꾸면 리스트 렌더가 깨질 수 있음
- out / release 상태는 체크 불가 유지
- toggleGroup()는 disabled checkbox 제외해야 함
- submitBulk()는 상태 검증 유지
