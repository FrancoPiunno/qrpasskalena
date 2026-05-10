# Sistema de Diseño QR Pass - Estética Premium Dark

Este documento establece el lenguaje visual y los patrones de diseño unificados para el dashboard de **QR Pass**, basado en la modernización implementada en `lista.html`.

---

## 1. Fundamentos Visuales

### Paleta de Colores
*   **Fondo Principal**: `#080808` (Negro profundo/OLED).
*   **Superficies (Cards/Modales)**: `#121212` con bordes sutiles `rgba(255,255,255,0.1)`.
*   **Texto Primario**: `#FFFFFF` (Blanco puro).
*   **Texto Secundario**: `rgba(255,255,255,0.6)` (Gris suave).
*   **Acentos Metálicos**: Degradados entre `#111` y `#BBB` para elementos destacados.

### Tipografía
*   **Fuente**: `Google Sans Flex` (o `Inter`/`Outfit` como fallback).
*   **Títulos**: Peso `500` (Medium), `letter-spacing: -0.5px`.
*   **Cuerpo/Botones**: Peso `400` (Regular).

---

## 2. Componentes de Interfaz

### Botones de Acción y Filtros (Unificados)
Todos los controles de la cabecera deben compartir estas dimensiones para una alineación perfecta:
*   **Altura (Height)**: `44px` constante.
*   **Radio de Borde (Border-radius)**: `50px` (Rounded-full).
*   **Padding**: `0 1.5rem` (Horizontal).
*   **Gap de Iconos**: `0.8rem`.

#### Variantes de Botón:
1.  **Primario (Crear)**: Fondo blanco, texto negro, sin borde.
2.  **Filtro/Tab**: Fondo `rgba(255,255,255,0.05)`, borde `1px solid rgba(255,255,255,0.1)`, texto blanco.
3.  **Activo**: Fondo blanco, texto negro (invierte el estilo del Tab).

### Iconografía
*   **Tamaño**: `22px x 22px`.
*   **Grosor de Trazo (Stroke-width)**: `2.2` para una apariencia moderna y definida.
*   **Color**: Heredado del texto del botón.

---

## 3. Estructura y Layout

### Espaciado (Grid & Margins)
*   **Contenedor Lateral**: `max-width: 1200px` (Desktop).
*   **Margen entre elementos de lista**: `1rem` o `1.5rem`.
*   **Padding de Página**: `2rem` en desktop, `1rem` en móvil.

### Cards (Tickets/Entradas)
*   **Border-radius**: `20px`.
*   **Hover**: Efecto de elevación suave o cambio de opacidad en el borde.
*   **Desktop**: Layout horizontal tipo tabla.
*   **Móvil**: Layout vertical con prioridad en el nombre.

---

## 4. Patrones de UX

### Búsqueda en Tiempo Real
*   **Desktop**: Botón de lupa circular que abre un modal burbuja centrado (`backdrop-filter: blur(8px)`). El filtrado debe ser instantáneo (`oninput`).
*   **Móvil**: Icono de lupa en la cabecera que expande un input de ancho completo.

### Estados de Feedback
*   **Valida**: Indicador verde suave (`#2ecc71` o similar en pill).
*   **Usada**: Indicador ámbar/amarillo (`#f1c40f` o similar en pill).

---

## 5. Reglas de Responsive
*   **Breakpoint**: `768px`.
*   **Hiding**: Usar las clases `.desktop-only` y `.mobile-only` con `display: none !important` para evitar duplicidad de controles visuales.
*   **Prioridad Móvil**: Las acciones primarias (Descargar Lista, Crear Entrada) deben convertirse en elementos de ancho completo o botones flotantes de fácil acceso.
