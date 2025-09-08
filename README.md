# Subscribe Bot

ТГ-бот, управляющий чатом и проверяющий участников чата на предмет подписки на канал.

## Принцип работы бота

Бот отслеживает пользователей в чате и канале, которые связаны друг с другом при помощи команды `/bind` (см. ниже). Бот не позволяет пользователям писать сообщения, пока они не подпишутся на канал.

## Как его использовать?

Предположим, вы администратор крупного чата, и вы хотите чтобы все участники чата также были подписаны и на ваш ТГ-канал. 

1. Сначала вам необходимо создать нового бота в [@BotFather](https://t.me/BotFather) и получить токен для дальнейшего использования.

![Этапы создания бота](https://github.com/kirich-yo/subscribe_bot/blob/main/assets/images/1.png)

2. Если у вас нет возможности развернуть бота на удаленном сервере, арендуйте или приобретите его. Найдите VDS-провайдера в вашем регионе и воспользуйтесь его услугами. Либо же разверните бота на своем собственном компьютере (временное и не совсем удобное решение). В идеале сервер должен работать на одном из дистрибутивов GNU/Linux.

3. На новом рабочем сервере установите Git и Docker.
Пример установки Git на Ubuntu 24.04:
```
sudo apt install git
```
Руководство по установке Docker на разные платформы есть на [официальном сайте документации](https://docs.docker.com/engine/install/).

4. Сделайте клон данного репозитория:
```
git clone https://github.com/kirich-yo/subscribe_bot.git
cd subscribe_bot/
```

5. Запишите токен бота и все остальные настройки в файл `.env`:
```
BOT_TOKEN=[токен вашего бота (обязательно)]
MESSAGE_TIMEOUT=[время, по истечению которого сообщения бота удаляются сами (в секундах)]
LOG_FILE_PATH=[путь к папке, в которой хранятся все логи бота]
```

6. Запустите процесс развертки в Docker Compose:
```
docker compose up
```
Данная команда при первом запуске выполняет все необходимые для работы бота подготовительные этапы.
Завершить его работу можно следующей командой:
```
docker compose down
```

7. Создайте сервис для systemd для полной автоматизации запуска/остановки бота (путь к файлу Docker Compose замените на ваш):
```ini
# /etc/systemd/system/subscribe-bot.service

[Unit]
Description=Subscribe Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c "docker compose -f /root/subscribe_bot/docker-compose.yml up --detach"
ExecStop=/bin/bash -c "docker compose -f /root/subscribe_bot/docker-compose.yml stop"

[Install]
WantedBy=multi-user.target
```
Включите автозапуск нового сервиса:
```
systemctl enable subscribe-bot.service
```
В дальнейшем вы его сможете запускать/останавливать следующими командами:
```
systemctl start subscribe-bot.service
systemctl stop subscribe-bot.service
```

8. Пригласите уже готового к использованию бота в свои чат и канал и назначьте права администратора:
