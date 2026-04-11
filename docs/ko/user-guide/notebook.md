# 노트북 인터페이스 (Notebook Surface)

이 페이지에서는 `ctx.notebook`을 설명합니다 — Jupyter 노트북과 IPython
환경에서 Contexta의 조사 인터페이스를 노출하는 파사드(facade) 프로퍼티입니다.

## 개요

`ctx.notebook`은 현재 `Contexta` 객체에 바인딩된 `NotebookSurface` 인스턴스를
반환합니다. HTML 프래그먼트를 빌드하거나 인라인으로 표시하는 편의 메서드를
제공합니다.

```python
from contexta import Contexta

ctx = Contexta(...)

# 노트북 셀에 런 스냅샷 인라인 표시
ctx.notebook.show_run("run:my-proj.run-01")
```

이 프로퍼티는 지연 초기화(lazy)됩니다 — `NotebookSurface`는 처음 접근 시
생성되며 이후 재사용됩니다.

---

## 메서드

### `show_run(run_id, *, display=True)`

런 스냅샷을 HTML 프래그먼트로 렌더링합니다.

- `display=True`(기본값)이고 IPython이 사용 가능하면,
  `IPython.display.display(HTML(...))` 을 호출하여 인라인 렌더링합니다.
- `.html`에 원시 HTML이 담긴 `NotebookFragment`를 반환합니다.

```python
fragment = ctx.notebook.show_run("run:my-proj.run-01", display=False)
print(fragment.html[:200])
```

### `compare_runs(left_run_id, right_run_id, *, display=True)`

두 런을 나란히 비교합니다.

```python
ctx.notebook.compare_runs(
    "run:my-proj.run-01",
    "run:my-proj.run-02",
)
```

### `show_metric_trend(metric_key, *, project_name=None, stage_name=None, query=None, display=True)`

런 전체에 걸친 메트릭 트렌드 차트를 렌더링합니다.

```python
ctx.notebook.show_metric_trend("accuracy", project_name="my-proj")
```

### `render(value)`

임의의 Contexta 결과 객체(스냅샷, 리포트, 비교)를 HTML 문자열로 렌더링합니다.

```python
snapshot = ctx.get_run_snapshot("run:my-proj.run-01")
html = ctx.notebook.render(snapshot)
```

### `to_pandas(value)` / `to_polars(value)`

Contexta 결과를 pandas 또는 polars DataFrame으로 변환합니다.

```python
# pandas 또는 polars 설치 필요
df = ctx.notebook.to_pandas(ctx.list_runs("my-proj"))
```

---

## IPython 가용성

`ctx.notebook`은 IPython 없이도 동작합니다.

- IPython이 **설치된** 경우: `show_*` 메서드가 `IPython.display`를 통해
  노트북 셀에 인라인 렌더링합니다.
- IPython이 **설치되지 않은** 경우: `show_*` 메서드가 `NotebookFragment`를
  반환하지만 표시하지 않습니다. 에러는 발생하지 않습니다.

---

## NotebookFragment

모든 `show_*` 메서드는 `NotebookFragment` 데이터클래스를 반환합니다:

```python
from contexta.surfaces.notebook import NotebookFragment

fragment: NotebookFragment = ctx.notebook.show_run(..., display=False)
fragment.html        # 원시 HTML 문자열
fragment.title       # 페이지/섹션 제목
fragment.metadata    # run_ref 등이 담긴 dict
```

---

## 직접 임포트

`NotebookSurface`와 헬퍼 함수들은 다음 경로로도 사용 가능합니다:

```python
from contexta.adapters.notebook import (
    NotebookSurface,
    NotebookFragment,
    display_run_snapshot,
    display_run_comparison,
    display_metric_trend,
    render_html_fragment,
    to_pandas,
    to_polars,
)
```

전체 `Contexta` 인스턴스 없이 인터페이스 함수만 필요할 때 권장되는 경로입니다.
