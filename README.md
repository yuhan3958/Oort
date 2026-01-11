# Oort: 새로운 마인크래프트 데이터팩 컴파일러

## 개요

**Oort**는 마인크래프트 데이터팩 작성을 위해 설계된  
**절차지향 프로그래밍 언어이자 컴파일러**입니다.

Oort는 기존 데이터팩의 문자열 기반 명령어 작성, `$` 기반 매크로,  
불명확한 구조를 언어 차원에서 제거하고  
데이터팩을 **명확한 프로그램 구조**로 작성할 수 있도록 하는 것을 목표로 합니다.

100% AI를 이용한 프로젝트입니다!

---

## 핵심 기능

### 1. 명령어는 내장 함수와 같다

Oort에서는 공백 기반 Minecraft 명령어 문법을 사용하지 않습니다.

```oort
say("Hello")
give(@p, "minecraft:diamond", 3)
```

모든 Minecraft 명령어는 함수 호출 형태로만 작성됩니다.

---

### 2. 모든 구조는 컴파일 타임에 결정된다

- import는 런타임 로딩이 아니다  
- 매크로는 런타임 함수가 아니다  
- 실행 중에 코드 구조는 변하지 않는다  

Oort의 모든 파일, 함수, 의존성, 매크로 확장은  
컴파일 시점에 완전히 확정됩니다.

---

### 3. 절차지향 언어

Oort는 객체지향 언어가 아닙니다.

- 함수 중심  
- 명확한 실행 흐름  
- 데이터팩 구조와 1:1 대응  

```oort
on load {
  init()
}

on tick {
  update()
}
```

---

## 프로젝트 구조

```text
project/
├─ properties.json
├─ src/
│  ├─ main.oort
│  └─ util/
│     └─ math.oort
└─ build/
   └─ <datapack_name>/
```

---

## properties.json

`properties.json`은 Oort 프로젝트의 설정 파일입니다.

```json
{
  "package": {
    "name": "comet",
    "namespace": "comet",
    "description": "Example Oort project"
  },
  "minecraft": {
    "version": "1.21.5"
  },
  "entrypoints": {
    "load": "src/main.oort",
    "tick": "src/main.oort"
  },
  "build": {
    "output": "build/",
    "datapack_name": "comet_datapack",
    "clean": true
  }
}
```

### pack_format 처리

- `minecraft.pack_format`을 입력하지 않아도 됨  
- `minecraft.version`을 기준으로 자동 추론  
- 알 수 없는 버전일 경우 컴파일 오류 발생  

---

## 문법 개요

### 함수

```oort
fn init() {
  say("Loaded")
}
```

---

### 조건문

```oort
if hp > 0 {
  say("Alive")
} else {
  say("Dead")
}
```

---

### 반복문

#### while

```oort
while hp > 0 {
  damage()
}
```

---

## import 시스템

```oort
from "util/math.oort" import clamp
from "util/math.oort" import lerp as linear
from "other.oort" import *
```

### 특징

- import는 파일, 함수, 조건문, 반복문 내부 어디에서든 사용 가능  
- import는 컴파일 타임 선언  
- 조건문 내부 import도 항상 컴파일 대상에 포함됨  

---

## 스코프와 이름 규칙

Oort는 렉시컬 스코프를 사용합니다.

- 파일 스코프  
- 함수 스코프  
- 블록 스코프  

### 이름 충돌 규칙

같은 스코프에서 같은 이름은 **무조건 컴파일 오류**입니다.

- 함수 / 변수 / import / 매크로 구분 없음  
- shadowing 없음  
- 덮어쓰기 없음  

```oort
from "a.oort" import update
from "b.oort" import update   // 오류
```

해결 방법:

```oort
from "a.oort" import update as updateA
from "b.oort" import update as updateB
```

---

## 매크로 (Macro)

Oort의 매크로는 **변수를 받을 수 있는 컴파일 타임 함수**입니다.

```oort
macro announce(msg) {
  say(msg)
}
```

사용:

```oort
announce("Hello")
```

### 매크로 특징

- `$` 기호 사용 없음  
- 일반 함수처럼 호출  
- 컴파일 타임 AST 확장  
- 런타임 비용 없음  
- 이름 충돌 규칙 동일 적용  

---

## Minecraft 명령어 호출

모든 Minecraft 명령어는 함수 호출 형태로 작성합니다.

```oort
say("Hello")
give(@p, "minecraft:diamond", 3)
kill(@e)
```

- 문자열 기반 명령어 작성 불가  
- 해석과 변환은 컴파일러의 책임  

---

## 컴파일러 사용법

```bash
python -m oortc build <project_dir>
```

옵션:

- `--out <dir>` : 출력 디렉터리 지정  

---

## 출력 예시

```text
build/comet_datapack/
├─ pack.mcmeta
└─ data/
   ├─ minecraft/
   │  └─ tags/functions/
   │     ├─ load.json
   │     └─ tick.json
   └─ comet/
      └─ functions/
         ├─ main/init.mcfunction
         ├─ main/update.mcfunction
         └─ util/math/clamp.mcfunction
```