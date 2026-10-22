# Обложки проекта

Обложка и примеры набраны настоящим Valera Sans поверх редактируемой HTML-композиции. Картины автора сохранены без перерисовки. Это оформление документации; обложки отрисованы шрифтом 0.6.3 (22.10.2026).

- `specimen/cover.html` — исходный макет обложки; `#examples` открывает два примера применения.
- `docs/assets/banner.webp`, `features.webp` — изображения для README, 1920 × 960.
- `specimen/social-preview.jpg` — обложка ссылки, 1280 × 640, меньше 1 МБ.
- `specimen/index.html` и корневая страница содержат Open Graph / Twitter Card с абсолютным адресом обложки на GitHub Pages.
- [Работы и авторство](../specimen/artworks/README.md).

Повторный рендер: установить зависимости Python и Node по [BUILD.md](BUILD.md), установить Chromium (`npx playwright install chromium`), затем выполнить `npm run showcase`. Для локального Chrome можно задать `CHROME_PATH`. Браузер загружает готовый файл шрифта, включая его кернинг и контекстные формы.

GitHub использует отдельную настройку обложки репозитория: **Settings → General → Social preview → Edit → Upload an image**. Загрузить `specimen/social-preview.jpg`. Изображение в README само по себе не меняет обложку ссылки на репозиторий. [Документация GitHub](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview).
