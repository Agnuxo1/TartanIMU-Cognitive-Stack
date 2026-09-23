# JEV Orchestrator

**Un plano de control acotado y determinista para flujos cognitivos.** JEV toma decisiones tipadas de enrutamiento y supervisión; el código de la aplicación impone límites, validación, ejecución, privacidad y autorización.

[Read this in English](README.md) · [Arquitectura](docs/ARCHITECTURE.md) · [Política de JEV](docs/JEV-POLICY.md) · [Seguridad](docs/SECURITY.md) · [Notas de versión](docs/releases/v4.0.0.md)

![JEV Orchestrator v4 — plano de control cognitivo con supervisión humana](assets/hero-v4.png)

> **v4.0.0 · Python 3.11+ · MIT**
>
> Implementación de referencia orientada a Windows. Las versiones históricas seleccionadas se conservan en [`versions/`](versions/).

## Qué aporta

Los flujos con varios modelos pueden repetir consultas, escalar sin pruebas o gastar de más. JEV Orchestrator separa el juicio semántico de la aplicación determinista de políticas:

- resuelve sin modelo las tareas deterministas que reconoce;
- agrupa en una petición tipada de JEV la selección de ruta y los criterios de éxito;
- empieza por Luna y solo escala a Sol y Astra cuando hay evidencia de insuficiencia;
- aplica límites por ejecución a llamadas, escalado, uso observado de tokens y checkpoints de JEV;
- permite revisiones independientes acotadas y consultivas, no sustitutos de una votación mayoritaria;
- omite el contenido libre de tareas/resultados de la telemetría y redacta patrones habituales de secretos.

![Ruta v4: ejecución determinista, decisión JEV, trabajadores acotados y puertas de evidencia](assets/architecture-v4.svg)

No es un modelo fundacional nuevo. Las probabilidades y la confianza de JEV son juicios, no garantías calibradas. El límite de tokens evita iniciar llamadas opcionales al alcanzar el uso observado; no es un límite duro impuesto al proveedor.

## Inicio rápido

El flujo empaquetado y probado está orientado a Windows. Clona el repositorio en una unidad con espacio (por ejemplo, `E:\JEV-Orchestrator`) y usa Python 3.11 o posterior.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
```

Ejecuta una tarea o consulta el conector común de JEV:

```bat
run.bat "Resume estos requisitos locales del proyecto"
run.bat connect
run.bat connect --remote
run.bat route "Elige un enfoque acotado para esta tarea"
run.bat thinktank "Compara dos opciones de alto impacto" --risk high --uncertainty 0.8
```

Las decisiones remotas de JEV necesitan una credencial de TypeSafe. En Windows, guárdala interactivamente en Credential Manager; se introduce sin mostrarla y nunca se incluye en argumentos de comandos ni en archivos del proyecto:

```powershell
.\.venv\Scripts\python.exe scripts\store_jev_credentials.py --profile profile-a
```

El helper interactivo solo funciona en Windows. `connect` sin `--remote` realiza diagnósticos locales; `probe` y el enrutamiento remoto sí consultan al proveedor y pueden consumir cuota. Antes de configurar credenciales, lee [`docs/JEV-POLICY.md`](docs/JEV-POLICY.md) y [`docs/SECURITY.md`](docs/SECURITY.md).

## Cuándo consultar a JEV

Conviene cuando una decisión semántica entre rutas disponibles, un cambio relevante de estado o un juicio compacto de finalización puede cambiar el siguiente paso. Es mejor usar código para transformaciones exactas, comprobaciones rutinarias, límites y control de acceso. Agrupa preguntas tipadas que comparten las mismas pruebas y evita sondear periódicamente un estado sin cambios.

![Política JEV: decisiones tipadas, escalado basado en evidencia y autorización humana](assets/jev-policy-v4.svg)

El thinktank opcional pregunta a JEV si merece la pena pagar el coste de más perspectivas. En v4 estas están limitadas; las ausentes o fallidas quedan como evidencia no resuelta y el panel es consultivo. Compras, publicación pública, entregas de concursos y otras acciones externas relevantes siguen requiriendo autorización humana según el flujo aplicable.

## Reto TartanIMU: pruebas y límites de la evidencia

El repositorio incluye **utilidades de contrato con datos sintéticos y sus pruebas** para formas de ventanas IMU, particiones agrupadas, detección de fugas y helpers de fórmulas. No incluye los datos oficiales del reto, un modelo o pesos entrenados para la competición, el evaluador oficial completo, una entrega válida ni una puntuación emitida por los organizadores. No se afirma puesto ni elegibilidad.

![Contrato de la tarea TartanIMU y evidencia necesaria para verificar una participación](assets/tartanimu-evidence.svg)

A fecha de 23-09-2026 no se pudo inspeccionar desde este entorno el historial privado de entregas de Kaggle. Los archivos locales no permiten concluir si el titular entregó a tiempo. La [página oficial](https://superodometry.com/imuchallenge/) y la [competición en Kaggle](https://www.kaggle.com/competitions/tartan-imu-challenge-iros2026) especifican requisitos y plazos; consulta la [nota de evidencia fechada](docs/TARTANIMU-STATUS-2026-09-23.md). Las pruebas sintéticas y las métricas locales no son resultados oficiales.

## Desarrollo

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q jev_orchestrator competitions\tartanimu
```

Las pruebas cubren enrutamiento, escalado acotado, credenciales, minimización de telemetría y contratos sintéticos de TartanIMU. Los benchmarks que consultan JEV o un modelo usan red y cuota; no forman parte de las pruebas unitarias. Consulta [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Estructura

- `jev_orchestrator/` — runtime v4, enrutador, supervisión, políticas y telemetría.
- `competitions/tartanimu/` — helpers de contratos sintéticos; no es una solución entrenada.
- `docs/` — arquitectura, seguridad, uso de JEV, evidencia del reto y notas de versión.
- `skills/typesafe-ai/` — guía local para usar el SDK TypeSafe.
- `versions/v2.0.0/`, `versions/v3.0.0/` — versiones históricas seleccionadas; v4 en la raíz es la mantenida.
- `assets/` — imagen de portada generada y tres diagramas explicativos.

La ilustración de portada se generó con OpenAI Image Generation; la interfaz no mostró el identificador del modelo. Los diagramas son material documental del proyecto. El software y la documentación se ofrecen bajo [licencia MIT](LICENSE); las dependencias conservan sus licencias propias.

## Licencia

MIT. Consulta [`LICENSE`](LICENSE).
