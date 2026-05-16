# Body Hero - Git/GitHub 연동 가이드

## 이미 완료된 것
- `project.godot` 프로젝트명 → **Body Hero** 로 변경됨
- `.gitignore`에 `tools/venv_ml/`, `venv/` 추가 (가상환경 제외)
- `git init` 실행됨 (저장소 생성됨)

## 폴더 이름 (현재)
프로젝트 폴더는 **body-hero** 기준입니다. 터미널/경로는 `c:\Users\User\Documents\body-hero` 를 사용하세요.

## GitHub 연동 (직접 실행할 명령)

**1) Lock 파일 정리**  
다른 Git 작업이 없다면, 탐색기에서 아래 파일이 있으면 삭제하세요.  
`body-hero\.git\index.lock`

**2) 터미널에서 프로젝트 폴더로 이동**
```powershell
cd "c:\Users\User\Documents\body-hero"
```

**3) 스테이징 & 첫 커밋**
```powershell
git add .
git commit -m "Initial commit: Body Hero project"
git branch -M main
```

**4) GitHub 원격 추가 (본인 아이디로 바꾸세요)**
```powershell
git remote add origin https://github.com/본인GitHub아이디/body-hero.git
```

**5) 푸시**
```powershell
git push -u origin main
```
비밀번호 대신 **Personal Access Token** 입력하라는 안내가 나오면,  
GitHub → Settings → Developer settings → Personal access tokens 에서 토큰을 만들고 입력하면 됩니다.

---

이후 다른 PC에서는:
```powershell
git clone https://github.com/본인GitHub아이디/body-hero.git
cd body-hero
```
작업 전에는 `git pull`, 작업 후에는 `git add .` → `git commit -m "메시지"` → `git push` 하면 됩니다.
