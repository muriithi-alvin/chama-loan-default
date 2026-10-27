# Fonts

Vendored so pages never call a font service (X9). Both are variable fonts
(every weight in one file), Latin subset, from the Fontsource copies of the
Google Fonts releases, under the SIL Open Font License 1.1 (licence texts
beside them).

| File | Font | Used for |
| --- | --- | --- |
| `gabarito-latin-wght.woff2` | Gabarito | Page titles and big numbers (700-800) |
| `atkinson-hyperlegible-next-latin-wght.woff2` | Atkinson Hyperlegible Next | Everything else (400, 700) |

Loaded with `next/font/local` in `src/app/layout.tsx`.
