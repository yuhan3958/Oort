# PRD – Oort Compiler

## 1. 개요 (Overview)

**Oort**는 Minecraft 데이터팩 생성을 목적으로 하는  
**절차지향 전용 컴파일 언어 및 컴파일러**이다.

입력은 `.oort` 소스 코드와 `properties.json`이며,  
출력은 **실행 가능한 Minecraft 데이터팩(pack.mcmeta, mcfunction, tags)**이다.

Oort의 목표는 기존 데이터팩의 문자열 기반 명령어 작성 방식과
불안정한 매크로 사용을 제거하고,
**명확하고 구조적인 언어**로 데이터팩을 작성할 수 있도록 하는 것이다.

---

## 2. 핵심 설계 철학

- 절차지향 언어 (객체지향 요소 없음)
- 모든 구조는 **컴파일 타임에 결정**
- 런타임 로딩, 리플렉션, 동적 구조 변경 없음
- Minecraft 명령어 문자열 작성 금지
- 해석의 책임은 전부 컴파일러에 있음

---

## 3. 프로젝트 구조

```
project/
 ├─ properties.json
 ├─ src/
 │   └─ *.oort
 └─ build/
     └─ <generated datapack>
```

---

## 4. properties.json 요구사항

properties.json은 다음 정보를 포함해야 한다.

- 패키지 네임스페이스
- Minecraft 버전
- entrypoints (load, tick)
- scoreboard objective 설정

### pack_format 규칙
- pack_format은 Minecraft 버전으로부터 **자동 추론**
- 알 수 없는 버전일 경우 컴파일 오류 발생

### scoreboard 설정
- objective 이름은 사용자 지정 가능
- 이미 존재하는 objective 재사용 가능
- create_if_missing 옵션 지원

---

## 5. 변수 모델 (매우 중요)

Oort에는 두 종류의 변수만 존재한다.

### int
- scoreboard 기반 정수
- 조건문, 반복문, 계산 전용
- 직접 리터럴 대입 불가
- 반드시 `toInt`를 통해서만 생성

### var
- storage 기반 데이터
- 문자열, 구조체, 배열, NBT, 좌표 등 모든 데이터
- 기본 변수 타입

---

## 6. 변환 규칙

### var → int
```
int x = toInt(varName, keyOrIndex)
```

- keyOrIndex는 문자열 키 또는 정수 인덱스
- var 내부 접근의 **유일한 방법**

### int → var
```
var v = toVar({ key: value, ... })
```

- toVar는 구조 생성자
- toVar(int) 형태는 금지

---

## 7. 좌표 시스템

좌표는 전부 `var` 기반 **Position 구조체**로 통일한다.

### Position 표준 구조
```
{ x, y, z }
```

### 내장 함수
- `position(entity) -> var(Position)`
- `positionxyz(x:int, y:int, z:int) -> var(Position)`

---

## 8. 문법 규칙

- 선언과 대입 동시 허용
```
int x = toInt(p, "x")
```

- 조건문
  - 조건식은 반드시 int

- 반복문
  - for (forEach 스타일)
  - while (int 조건)

- 같은 스코프에서 같은 이름은 **무조건 컴파일 오류**
  - 변수 / 함수 / 매크로 / import 전부 포함

---

## 9. import 시스템

문법:
```
from "path.oort" import name
from "path.oort" import *
```

규칙:
- import는 어디서든 가능 (함수/조건/반복문 내부 포함)
- import는 항상 컴파일 타임 포함
- 조건부 import는 없음

---

## 10. Minecraft 명령어 호출 규칙

- 모든 Minecraft 명령어는 **함수 호출 형태**로만 작성
```
say("hello")
give(@p, "minecraft:diamond", 3)
```

- 인자 순서는 Minecraft 원본 명령어 순서를 그대로 따른다

- 다형적인 명령어(tp 등)는 명시적으로 분리
```
tpPosition(target, x, y, z)
tpUser(target, destination)
```

---

## 11. execute DSL

execute는 문자열이 아니라 **실행 컨텍스트 블록**이다.

문법:
```
execute(as(target), at(target), ...) {
    statements
}
```

규칙:
- modifier 순서는 사용자가 어떻게 써도 됨
- 컴파일러가 Minecraft 규칙에 맞게 재정렬
- 중첩 execute는 flatten하여 하나로 합침
- 블록 내부의 @s는 execute context에 따라 의미가 바뀜

---

## 12. 매크로 시스템

Oort 매크로는 **Minecraft Function Macro**로 출력한다.

Oort:
```
macro announce(msg) {
  say(msg)
}
```

출력 mcfunction:
```
$say $(msg)
```

호출 방식:
- storage에 인수 NBT 생성
- `function <path> with storage <namespace>:oort tmp.macro_args`

매크로는 런타임 함수가 아니며,
치환은 Minecraft 매크로 시스템에 맡긴다.

---

## 13. 표준 내장 함수 (Standard Builtins)

자주 쓰이는 패턴은 표준 내장 함수로 제공한다.

예시:
- position
- positionxyz
- getBlock(pos)
- collisionCircle(entity, radius, type)
- collisionSquare(entity, size, type)
- actionbar(target, textVar)

내장 함수는 내부적으로 여러 mcfunction을 생성할 수 있다.

---

## 14. 컴파일러 구현 요구사항

- 구현 언어: Python
- 주요 단계:
  1. properties.json 로드
  2. import 그래프 수집
  3. 파싱 (AST 생성)
  4. 스코프 및 이름 검사
  5. 매크로 처리
  6. execute flatten
  7. int/var backend 결정
  8. IR 생성
  9. mcfunction / tag / pack.mcmeta 출력

---

## 15. 목표 (Goals)

- 실제 Minecraft에서 동작하는 데이터팩 생성
- 문법 일관성과 명시성을 최우선
- 컴파일러 구현 용이성 중시
- 실사용 가능한 언어 완성

---

## 16. 비목표 (Non-Goals)

- 객체지향
- 타입 시스템
- 런타임 동적 기능
- 하위 Minecraft 버전 호환