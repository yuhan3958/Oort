# Oort 컴파일러: 코드 생성 설명

이 문서는 Oort 컴파일러가 어떻게 특수 문법들을 실제 Minecraft 명령어로 대체하여 생성하는지 설명합니다.

### 1. 변수 관리 (`AssignmentStatement`)

Oort의 변수는 단일 scoreboard objective에 저장된 score로 구현됩니다.

- **Objective 생성**: `emitter.py`에 `VARS_OBJECTIVE = "oort_vars"` 상수가 정의됩니다. `visit_OnBlock` 메서드는 `on load` 함수의 시작 부분에 `scoreboard objectives add oort_vars dummy` 명령어를 삽입하도록 수정되었습니다. 이를 통해 변수가 사용되기 전에 objective가 반드시 존재하도록 보장합니다.
- **할당 로직**: emitter의 `visit_AssignmentStatement` 메서드는 이제 `scoreboard players` 명령어를 생성합니다.
    - **리터럴 할당 (`x = 10`)**: `scoreboard players set x oort_vars 10`을 생성합니다.
    - **변수 할당 (`x = y`)**: `scoreboard players operation x oort_vars = y oort_vars`를 생성합니다.
    - **표현식 할당 (`x = y + 1`)**: 명령어 시퀀스를 생성합니다. 먼저 값을 복사하고 (`scoreboard players operation x oort_vars = y oort_vars`), 그 다음 연산을 수행합니다 (`scoreboard players add x oort_vars 1`).

### 2. 조건문 (`IfStatement`)

`if condition...`은 `execute if score` 명령어와 본문을 위한 별도 함수의 조합으로 대체됩니다.

- **본문 함수 생성**: `visit_IfStatement`에서 `if` 문의 본문(`node.if_body`)이 추출되어 고유한 이름의 새 함수(예: `if_body_1`)를 생성하는 데 사용됩니다.
- **조건부 실행**: `_format_condition` 헬퍼 메서드는 Oort 표현식(예: `count < 5`)을 Minecraft `execute if score` 하위 명령어로 변환합니다. 생성된 명령어는 새로 만들어진 본문 함수를 실행합니다.
    - `count < 5`는 `execute if score count oort_vars matches ..4 run function <namespace>:if_body_1`이 됩니다.
    - `x >= y`는 `execute if score x oort_vars >= y oort_vars run function <namespace>:if_body_1`이 됩니다.

### 3. `while` 반복문

`while` 반복문은 가장 복잡한 변환으로, 두 개의 함수를 사용하여 자체적으로 스케줄링하는 루프를 생성합니다.

- **Check 및 Body 함수**: `visit_WhileStatement`에서 "check" 함수와 "body" 함수라는 두 개의 새로운 함수가 생성됩니다.
- **Body 함수**: emitter는 Oort `while` 블록의 모든 문장을 포함하는 body 함수를 먼저 생성합니다. 핵심적으로, 이 함수 끝에 `schedule function <check_func_name> 1t` 명령어를 추가하여 다음 게임 틱에 루프가 계속되도록 합니다.
- **Check 함수**: 그 다음 emitter는 check 함수를 생성합니다. 이 함수는 루프 조건을 확인하는 단일 `execute if score ...` 명령어를 포함합니다. 조건이 충족되면 body 함수를 호출합니다.
- **최초 호출**: 원래의 Oort `while` 반복문은 루프를 처음 시작하는 단일 `function <check_func_name>` 호출로 대체됩니다.

### 4. 사용자 정의 함수 호출

`# TODO: unresolved call to function`은 적절한 `function` 명령어로 대체됩니다.

- **심볼 해석**: 핵심적인 변경 사항은 매크로 확장 *후에* 심볼 테이블을 빌드하는 것이었습니다. 이를 통해 모든 AST 노드의 `scope` 속성이 최종 AST에 대해 올바르게 설정되도록 보장합니다.
- **경로 계산**: `visit_CallStatement`에서 호출된 함수가 내장 함수가 아니면 `_find_function_path`를 호출합니다. 이 헬퍼는 `node.scope`를 사용하여 호출된 함수에 대한 심볼을 찾습니다.
- **Symbol의 `module_path`**: `Symbol` 객체는 이제 자신이 정의된 파일의 `module_path`를 저장합니다. `_find_function_path`는 이 저장된 경로를 사용하여 전체 네임스페이스가 포함된 함수 이름(예: `oort2_example:src/load/setup`)을 계산하고, 최종 `function` 명령어를 생성하는 데 사용합니다.
