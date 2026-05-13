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

## 1 ошибка вида "API accepted schema-violating request"

Ошибка валидации/типизации

### v2/users/me/config

Принимает значение false числового параметра page

repro: '/api/v2/users/me/config/?page=false'

## 3 ошибки вида "Internal Server Error"

Все 3 ошибки являются ошибками валидации

В schemathesis отчёте каждая из ошибок имеет три отметки:

- Server Error, так как в ответ приходит Internal Server Error
- Undocumented Content-Type Received, так как 500 приходит в виде HTML
- Undocumented HTTP status code, так как ошибка 500 не занесена в openapi

### api/v2/comments

Internal server error вызванный некорректной валидацией данных запроса

repro: api/v2/comments/?comment_id=-29114&ordering=%C3%80%C2%B9%22%F1%87%97%8A%13%C3%96%C2%95v%28%5B%C3%90%C2%93%C2%97%C3%B5

### api/v2/users

Internal server error вызванный некорректной валидацией данных запроса

repro: api/v2/users/?email=%C3%B2p%F1%A7%82%98%C3%91%05O%C3%AC6%29r%C2%98%C3%8C%2B7%C3%A8%C2%96%F3%B0%A1%82%F1%90%BF%B6%25&is_superuser=5n%C2%BE%C2%94%C2%90%C3%B3%C2%A5%C2%B6%C3%81%C2%A4n4x%C2%ADD%C2%96%C2%9D%F0%A7%AA%BE%3D%C3%A2%F1%84%BC%A2%C2%80%C2%87h%C3%B0%C2%95%C3%A3M%F3%AC%BF%8A%10&exclude_external=-0.5&project=9%C2%A7%F2%82%87%96&username=&is_active=0&last_name=%E1%B9%B0%CC%BA%CC%BA%CC%95o%CD%9E+%CC%B7i%CC%B2%CC%AC%CD%87%CC%AA%CD%99n%CC%9D%CC%97%CD%95v%CC%9F%CC%9C%CC%98%CC%A6%CD%9Fo%CC%B6%CC%99%CC%B0%CC%A0k%C3%A8%CD%9A%CC%AE%CC%BA%CC%AA%CC%B9%CC%B1%CC%A4+%CC%96t%CC%9D%CD%95%CC%B3%CC%A3%CC%BB%CC%AA%CD%9Eh%CC%BC%CD%93%CC%B2%CC%A6%CC%B3%CC%98%CC%B2e%CD%87%CC%A3%CC%B0%CC%A6%CC%AC%CD%8E+%CC%A2%CC%BC%CC%BB%CC%B1%CC%98h%CD%9A%CD%8E%CD%99%CC%9C%CC%A3%CC%B2%CD%85i%CC%A6%CC%B2%CC%A3%CC%B0%CC%A4v%CC%BB%CD%8De%CC%BA%CC%AD%CC%B3%CC%AA%CC%B0-m%CC%A2i%CD%85n%CC%96%CC%BA%CC%9E%CC%B2%CC%AF%CC%B0d%CC%B5%CC%BC%CC%9F%CD%99%CC%A9%CC%BC%CC%98%CC%B3+%CC%9E%CC%A5%CC%B1%CC%B3%CC%ADr%CC%9B%CC%97%CC%98e%CD%99p%CD%A0r%CC%BC%CC%9E%CC%BB%CC%AD%CC%97e%CC%BA%CC%A0%CC%A3%CD%9Fs%CC%98%CD%87%CC%B3%CD%8D%CC%9D%CD%89e%CD%89%CC%A5%CC%AF%CC%9E%CC%B2%CD%9A%CC%AC%CD%9C%C7%B9%CC%AC%CD%8E%CD%8E%CC%9F%CC%96%CD%87%CC%A4t%CD%8D%CC%AC%CC%A4%CD%93%CC%BC%CC%AD%CD%98%CD%85i%CC%AA%CC%B1n%CD%A0g%CC%B4%CD%89+%CD%8F%CD%89%CD%85c%CC%AC%CC%9Fh%CD%A1a%CC%AB%CC%BB%CC%AF%CD%98o%CC%AB%CC%9F%CC%96%CD%8D%CC%99%CC%9D%CD%89s%CC%97%CC%A6%CC%B2.%CC%A8%CC%B9%CD%88%CC%A3

### api/v2/testplans/assignee-progress

Internal server error вызванный некорректной валидацией данных запроса

repro: api/v2/testplans/assignee-progress/?assignee=-1.175494351e-38&parent=%C2%B0&project=-1.538943351812224e%2B114

## 9 ошибок вида "Response violates schema"

Ошибки указывающие на неточности в openapi.

### api/v2/testplans/labels

Response violates schema №1

Пустой ответ возвращает [], вместо объекта описанного в API

### api/v2/labels/deleted

Response violates schema №2

Возвращает объект вместо массива описанного в API

### api/v2/statuses/deleted

Response violates schema №3

Возвращает объект вместо массива описанного в API

### api/v2/projects

Response violates schema №4

Возвращает значения числового типа где должен возвращать строки по API

### api/v2/users/me

Response violates schema №5

Ошибка API

"count" is a required property, но отсутствует в выводе

repro: api/v2/users/me/

### api/v2/users/me/config

Response violates schema №6

Ошибка API

"count" is a required property, но отсутствует в выводе

repro: api/v2/users/me/config/?page=19959&page_size=-85'

### api/v2/users/

Response violates schema №7
Response violates schema №8

TestY разрешил регистрацию пользователя с имением 'eĐċ', что не разрешено
регулярным выражением ограничивающем username из OpenAPI

### api/v2/users/me

Response violates schema №9

TestY разрешил регистрацию пользователя с имением 'EąĻŨ40Ħ', что не разрешено
регулярным выражением ограничивающем username из OpenAPI


## 43 ошибки вида "API rejected schema-compliant request"

- 19 ошибок требования поля instance_ids в endpoints без этого поля в описании.
  - api/v2/cases/archive/restore/
  - api/v2/cases/deleted/recover/
  - api/v2/cases/deleted/remove/
  - api/v2/labels/deleted/recover/
  - api/v2/labels/deleted/remove/
  - api/v2/projects/archive/restore/
  - api/v2/projects/deleted/recover/
  - api/v2/projects/deleted/remove/
  - api/v2/statuses/deleted/recover/
  - api/v2/statuses/deleted/remove/
  - api/v2/suites/deleted/recover/
  - api/v2/suites/deleted/remove/
  - api/v2/suites/deleted/remove/ 
  - api/v2/testplans/archive/restore/
  - api/v2/testplans/deleted/recover/
  - api/v2/tests/archive/restore/
  - api/v2/tests/deleted/recover/
  - api/v2/tests/deleted/remove/
- Отсутствие ограничений в API
  - api/v2/suites/ ограничения поля ordering не указаны в API
  - api/v2/labels/ ограничения поля ordering не указаны в API
  - api/v2/labels/ ограничения поля project не указаны в API
  - api/v2/results/ ограничения поля project не указаны в API
  - api/v2/results/ ограничения поля test не указаны в API
  - api/v2/testplans/assignee-progress/ ограничения поля parent не указаны в API
  - api/v2/statuses/ ограничения поля color не указаны в API
  - api/v2/suites/union/ ограничения поля parent не указаны в API
  - api/v2/testplans/union/ ограничения поля parent не указаны в API
  - api/v2/comments обязательное применение полей model и object_id вместе не указано в API
  - api/v2/testplans/labels/ ограничения поля parent не указаны в API
  - api/v2/attachments/ ограничения поля parent не указаны в API
  - api/v2/users ограничения exclude_external не указаны в API
- Некорректное ограничение в API
  - api/v2/users/ минимальная длина пароля в API - 1; при таком запросе выдаётся ошибка Bad Request
- Bad Request вместо Not Found
  - api/v2/results/ приводит ошибку "Could not retrieve test from request" с кодом 400
- api/v2/tests
  - Ошибка 400 'Enter a number' для запроса в котором указаны все обязательные параметры

## 59 ошибок вида "Undocumented HTTP status code"

Указывает не незаполненные возможные кода возврата в эндпоинтах.

- Ошибка 400 не указана в возможных кодах возврата для всех эндпоинтов
- Ошибка 401 не указана в возможных кодах возврата для всех эндпоинтов
- Ошибка 404 не указана в возможных кодах возврата для всех эндпоинтов
- Ошибка 500 не указана в возможных кодах возврата для всех эндпоинтов
