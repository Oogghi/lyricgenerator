# 🎶 Generador de letras por Oogghi

Aplicación PyQt6 para crear vídeos karaoke con sincronización automática de letras y efectos visuales.

![Interfaz de la aplicación](screenshot.png)

## ✨ Funcionalidades

- **Sincronización automática** de letras con audio mediante ForceAlign
- **Soporte multi-formato**: MP3, WAV, FLAC, M4A, MP4, MOV, AVI
- **Descarga integrada desde YouTube** para audio y vídeo de fondo
- **Recorte de audio** con códigos de tiempo (MM:SS o H:MM:SS)
- **Superposición de vídeo** con efecto chroma key personalizable
- **Interfaz moderna** con barra de título personalizada
- **Guardado automático** de configuración
- **Codificación optimizada** (CPU/GPU: NVIDIA, AMD, Intel)

## 🛠️ Instalación

### Requisitos
- Python 3.8+
- FFmpeg instalado y accesible en PATH
- GPU opcional para codificación acelerada

### Dependencias
- Instaladas al iniciar la aplicación

### Estructura del proyecto
├── main.py # Interfaz principal
├── align_whisperx.py # Módulo de sincronización
├── generate_vid.py # Generación de vídeo de letras
├── chroma_video.py # Superposición chroma key
├── fonts/ # Carpeta de fuentes (.ttf/.otf)
│ └── COMICBD.ttf # Fuente por defecto
├── songs/ # Carpeta de sonidos
└── settings.json # Configuración guardada

## 🚀 Uso

1. **Lanzar la aplicación**
   - Hacer clic en "start.bat"

2. **Configurar el proyecto**
   - Seleccionar un archivo de audio o pegar un enlace de YouTube
   - Opcional: definir inicio/fin (ej.: `1:30` a `3:45`)
   - Introducir o pegar las letras en el cuadro de texto
   - Elegir carpeta de salida

3. **Vídeo de fondo (opcional)**
   - Seleccionar un vídeo local o enlace de YouTube
   - Ajustar parámetros de chroma key si es necesario

4. **Configuración avanzada**
   - **FPS**: fotogramas por segundo (predeterminado: 60)
   - **Inicio vídeo de fondo**: punto inicial en segundos
   - **Velocidad**: multiplicador de velocidad (1.25 = 125%)
   - **Similaridad/Fusión**: parámetros chroma key
   - **Fuente**: elegir entre las fuentes de `fonts/`
   - **Codificador**: seleccionar CPU o GPU según hardware

5. **Generar**
   - Hacer clic en "Generar vídeo karaoke"
   - Seguir progreso en barra de estado

## 📁 Archivos generados

Por cada proyecto, la aplicación crea:
- `[nombre]_trimmed.mp3` - Audio recortado
- `[nombre].lrc` - Archivo de sincronización
- `[nombre]_lyrics.mp4` - Vídeo solo con letras
- `[nombre]_final.mp4` - Vídeo final con fondo (si aplica)

## ⚙️ Configuración técnica

### Codificadores soportados
- **CPU**: libx264, libx265, mpeg4, vp8, vp9, av1
- **NVIDIA**: h264_nvenc, hevc_nvenc
- **AMD**: h264_amf, hevc_amf
- **Intel**: h264_qsv, hevc_qsv

### Presets de calidad
`ultrafast` → `veryslow` (velocidad vs calidad)

### Formatos de código de tiempo aceptados
- `MM:SS` o `M:SS` (ej.: `1:30`, `12:45`)
- `H:MM:SS` (ej.: `1:12:30`)
- `-1` para "hasta el final"

## 🎨 Personalización

### Añadir fuentes
1. Colocar archivos `.ttf` o `.otf` en carpeta `fonts/`
2. Reiniciar la aplicación
3. La fuente aparecerá en el desplegable

### Parámetros chroma key
- **Similaridad** (0.0-1.0): sensibilidad de detección de verde
- **Fusión** (0.0-1.0): suavidad de bordes
- **Velocidad**: controla velocidad del vídeo de fondo

## 🔧 Solución de problemas

### "❌ Error descarga audio/vídeo"
- Verificar conexión a internet
- Asegurar que el enlace de YouTube es válido y público

### "❌ Error recorte audio"
- Verificar que el archivo de audio no esté corrupto
- Asegurar que FFmpeg esté instalado

### Rendimiento lento
- Usar preset más rápido (`ultrafast`)
- Reducir FPS para pruebas

## 📋 Ejemplo de uso

Audio : https://www.youtube.com/watch?v=dQw4w9WgXcQ
Inicio : 0:15
Fin : 3:30
Letras :
Primera línea de la canción
Segunda línea con sincronización
Tercera línea final

Vídeo de fondo : https://www.youtube.com/watch?v=dQw4w9WgXcQ
Parámetros : FPS=60, Velocidad=1.25, Fuente=COMICBD

## 🤝 Contribución

¡Las contribuciones son bienvenidas! No dudes en:
- Reportar errores vía Issues
- Proponer mejoras
- Enviar Pull Requests

## 📧 Contacto

Creado por **Oogghi**

---

*Interfaz moderna con barra de título personalizada y guardado automático de configuración*
