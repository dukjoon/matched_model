# `matched_model`

> **AI Model Right-Sizing ("적정기술") Platform & Agent Skill** — 다수의 AI 벤치마크 사이트를 통합·보정·영역별 재계산하여, 작업 단계(`plan => implement`)에 가장 적합하고 비용 효율적인 모델과 추론 강도(`Low → Med → High → Max`)를 매칭합니다.

---

## 핵심 기능

1. **다중 벤치마크 통합 & 공통 모델 자동 편입 (Consensus Discovery)**
   - **7개 벤치마크 소스** 수집 및 정규화:
     - [DeepSWE](https://deepswe.datacurve.ai/) (`agentic_swe`, `cli_execution`)
     - [Artificial Analysis](https://artificialanalysis.ai/models) (`reasoning_planning`, `code_generation`, 비용/속도)
     - [SWE-bench Verified](https://www.swebench.com/) (`agentic_swe`, `code_generation`)
     - [LiveBench](https://livebench.ai/) (`reasoning_planning`, `code_generation`)
     - [Aider Polyglot](https://aider.chat/docs/leaderboards/) (`code_generation`, `agentic_swe`)
     - [Terminal-Bench](https://www.tbench.ai/) (`cli_execution`, `agentic_swe`)
     - [LMSYS Chatbot Arena](https://lmarena.ai/) (`reasoning_planning`, `code_generation`)
   - 여러 벤치마크 사이트(`>= 2`개)에서 공통으로 관측되는 모델은 별칭(Alias) 매핑을 거쳐 자동으로 활성 모델 로스터에 추가됩니다.

2. **단순 평균이 아닌 영역별 보정 및 순위 재계산 (Domain-Aware Re-Ranking)**
   - 벤치마크마다 테스트하는 영역과 점수 체계(Elo, Pass%, Index)가 다르기 때문에 단순 평균을 내지 않습니다.
   - 각 벤치마크 내 코호트 **Z-Score + Tanh 보정**으로 스케일을 맞춘 뒤, 작업 프로파일(`plan`, `implement`, `debug`, `trivial`)별 **역량 가중치 행렬**로 순위를 재계산합니다.

3. **적정기술(Right-Sizing) 추천 & Agent Skill (`Plan → Implement` 게이트)**
   - 무조건 최고가/최고점 모델을 고르는 대신, **품질 하한선(Quality Floor)** 을 통과하는 **Pareto 최적·최소 비용** `(모델, 추론 강도)`를 추천합니다.
   - `skills/matched-model/SKILL.md`를 Antigravity, Claude Code, Codex CLI 등에 등록하여 `plan => implement` 전환 시 과도한 모델(Overkill) 또는 성능 미달 모델(Underkill) 사용을 방지합니다.

4. **주 1회 자동 업데이트 & 즉시 배포**
   - `.github/workflows/update-benchmarks.yml`: 매주 월요일 `main` 브랜치에 최신 벤치마크 데이터(`data/benchmarks.json`, `data/routing_rules.json`, `docs/data/benchmarks.json`)를 자동 커밋합니다.
   - `.github/workflows/deploy-pages.yml`: `docs/index.html` 대시보드를 **GitHub Pages**에 즉시 배포합니다.

---

## 빠른 시작 (Quickstart)

```bash
# 1. 패키지 설치 (로컬)
pip install -e ".[scraping,dev]"

# 2. 벤치마크 수집 및 재계산 (오프라인 스냅샷 테스트: --offline)
matched-model update --offline

# 3. 단일 작업 모델 추천 (Overkill/Underkill 진단 포함)
matched-model recommend --phase implement --complexity medium --current-model claude-opus-5.5

# 4. Plan 마크다운 전체 단계별 모델 라우팅 테이블 생성
matched-model plan-check --file path/to/implementation_plan.md
```

### AI Agent Skill 등록

```bash
# 현재 워크스페이스(.agents/skills, .claude/skills, .codex/skills)에 등록
matched-model install-skill --target all --scope workspace

# 전역(~/.gemini/config/skills, ~/.claude/skills, ~/.codex/skills)에 등록
matched-model install-skill --target all --scope global
```

### GitHub 즉시 배포 방법

```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```
GitHub 저장소 **Settings → Pages → Source**를 **GitHub Actions**로 선택하면 `docs/index.html` 대시보드가 즉시 배포됩니다. (선택 사항: `ARTIFICIAL_ANALYSIS_API_KEY`를 Repository Secret으로 등록하면 live API 수집이 활성화됩니다.)
