# Аутентификация

Для аутентификации запросов schemathesis к TestY, необходимо использовать hook,
который будет получать токен авторизации перед запросом и добавлять его в
запрос, пример такого хука находится в файле hooks.py в одной директории с
данным readme.

В хуке на данный момент используемые логин и пароль указанны напрямую.

Документация к хукам:
https://schemathesis.readthedocs.io/en/latest/reference/hooks/

# Запуск

```sh
SCHEMATHESIS_HOOKS="hooks.py"  schemathesis run --phases stateful 'http://testy/api/v2/swagger/?format=openapi'
```

- SCHEMATHESIS_HOOKS - указывает путь к python файлу с хуками
- phases - выбирает режим работы schemathesis


# Результаты

Результаты предоставлены в файле ./schemathesis-report/junit-20260502T151322Z.xml

Присутствуют следующие виды ошибок:

## API rejected schema-compliant request

Ошибки указывающие на неточности в openapi.
Например, отсутвие границ входных значений.

## API accepted schema-violating request

Игнорирвание некорректных параметров.

## Response violates schema

Ошибки указывающие на неточности в openapi.

## Undocumented HTTP status code

Указывает не незаполненные возможные кода возврата в эндпоинтах.

## Server error Undocumented Content-Type

Указывает на случаи где nginx не проксировал запрос к бекенду.
