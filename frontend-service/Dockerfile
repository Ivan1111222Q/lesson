FROM nginx:mainline-alpine3.22-perl

# Копируем свой конфиг поверх дефолтного
COPY nginx.conf /etc/nginx/nginx.conf

# (необязательно) Копируем файлы сайта
COPY . /usr/share/nginx/html

# Открываем порт
EXPOSE 80

# Стартуем Nginx в форграунде
CMD ["nginx", "-g", "daemon off;"]