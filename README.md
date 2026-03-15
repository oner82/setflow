# SetFlow Clean Base 0316

현재 동작 기준으로 정리한 클린 베이스다.
실행에 필요한 파일만 남기고, 예전 패치 README/스니펫/캐시 파일은 제거했다.

## 실행
```bash
python -m uvicorn app:app --reload
```

## 접속
- 로그인: http://127.0.0.1:8000/login

## 현재 살아있는 화면
- OR 사용 등록: `/or-use`
- CSR 처리: `/csr`
- CSR 조회(OR 전용): `/csr-view`
- 관리자: `/admin`

## 정리 원칙
- 현재 라우트와 연결된 템플릿만 유지
- 패치용 README, 스니펫, 캐시, 임시 파일 제거
- 메뉴도 실제 살아있는 화면만 노출
