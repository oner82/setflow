# SetFlow Render 배포

## 1) GitHub 업로드
이 폴더 전체를 새 GitHub 저장소에 올립니다.

## 2) Render에서 배포
- Render 로그인
- New + -> Blueprint 선택
- GitHub 저장소 연결
- `render.yaml` 인식 확인
- 배포 실행

## 3) 주의
- 이 프로젝트는 SQLite를 사용하므로 **Persistent Disk가 꼭 필요**합니다.
- `SETFLOW_DB_PATH`는 `/var/data/setflow.db`로 이미 설정되어 있습니다.
- 초기 비밀번호는 `OR_PIN=1234`, `CSR_PIN=5678`, `ADMIN_PIN=0000` 입니다.
- 실제 사용 전에는 Render 환경변수에서 비밀번호를 바꾸세요.

## 4) 접속
배포 완료 후 Render가 발급한 URL로 접속하면 됩니다.
