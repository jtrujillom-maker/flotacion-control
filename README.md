# Banco de flotación: motor matemático en Python

Modelo, simulación, control, validación, API e interfaz web. Todo el cálculo se ejecuta en Python. El motor y el servidor de desarrollo no necesitan dependencias externas; Python 3.10 o superior.

## Ejecutar

Desde esta carpeta:

```powershell
python -m unittest discover -s tests -v
python validate.py
python run.py --output results
python run.py --plant geometric --output results_geometric
python app.py
```

Servidor local e interfaz HTML: http://127.0.0.1:8000. El archivo `server.py` conserva la API original; `app.py` es la aplicación WSGI completa con interfaz y API. Para verificar HTTP real, ejecutar `python smoke_http.py http://127.0.0.1:8000` mientras la aplicación está encendida.

La interfaz incluye edición de consignas, alimentación, perturbación, ruido y parámetros de control; selección de planta; gráficos de nivel y caudal; tabla de IAE; descarga CSV y cálculo SIMC en Python. Su vista de celdas muestra el último estado calculado, no una transmisión experimental en tiempo real.

### Servidor de producción

Linux / Render:

```sh
pip install -r requirements.txt
gunicorn app:application --bind 0.0.0.0:$PORT --workers 2 --timeout 60
```

Windows, si se quiere usar Waitress en lugar del servidor de desarrollo:

```powershell
pip install -r requirements.txt
waitress-serve --listen=127.0.0.1:8000 app:application
```

Publicación pendiente de crear el repositorio GitHub `flotacion-control` y desplegarlo en Render. No se ha creado ni verificado una URL pública. El usuario autorizó el espacio `My Workspace` y el plan gratuito. No se necesita base de datos ni variables secretas para este simulador.

API:

- GET /health: estado del motor.
- GET /api/config: parámetros por defecto.
- POST /api/simulate: simulación individual con parámetros JSON.
- POST /api/compare: PI, PI con feedforward literal y PI con feedforward respecto al equilibrio.
- POST /api/tune: cálculo SIMC; cuerpo con `k_prime`, `delay_s` y opcionalmente `tau_c_s`.

Ejemplo de cuerpo JSON:

```json
{"duration":600,"plant":"published","strategy":"pi_ff_nominal","noise_std_cm":0.02,"seed":42}
```

El resultado contiene series temporales, órdenes antes y después de saturación, acción anticipativa, parámetros, supuestos y métricas por celda. `status` indica si terminó o cruzó un límite físico. No se recorta artificialmente el nivel para ocultar vaciado o desbordamiento.

## Modelo

Fuente: Quintanilla et al., MethodsX 10 (2023), 102081, DOI 10.1016/j.mex.2023.102081, Tabla 2 y ecuaciones 7–9.

Unidades: nivel cm, caudal L/min, tiempo s. Para desviaciones respecto al equilibrio:

    dh_i/dt = b * [(qin_i(t-delay_in_i)-qin_i*) - (qout_i(t-delay_out_i)-qout_i*)]

En `published`, b=0.001018 cm/s por L/min. Retardos de salida: 7, 6 y 3 s. La sensibilidad de entrada igual a la de salida es un supuesto añadido; el artículo no la identifica separadamente. Los retardos de entrada son configurables e inicialmente nulos. Son retardos efectivos de trayectoria, sin inventarios explícitos de tuberías.

En `geometric`, b=1000/(60*A), A=900 cm², es decir b=0.0185185. Con rebose líquido constante, la ecuación equivale al balance qin-qout-qoverflow. No modela retención de gas, espuma ni cinética mineral. Los dos modelos tienen ganancias distintas y NO se mezclan.

Discretización Euler con dt configurable (máximo 1 s); retardos múltiplos enteros de dt. La integración conserva el estado inicial durante el historial previo. Las órdenes se calculan desde celda 1 a 3 en cada muestra; todas las plantas avanzan simultáneamente. El caudal de entrada usado por el controlador es la orden de la bomba anterior, no un caudalímetro independiente.

## Control

    error = setpoint - nivel_filtrado
    q_raw = q_equilibrio + Kc*error + integral + feedforward
    integral_next = integral + Kc*dt*error/Ti

Kc=(-62,-76,-85), Ti=(56,30,44), Kff=(0.8,0.8,1). Las ganancias se usan como referencias publicadas y no se resintonizan automáticamente para el modelo geométrico.

Estrategias:

- pi: feedforward=0.
- pi_ff_literal: Kff*(qin[k]-qin[k-1]), lectura literal de la ecuación 8.
- pi_ff_nominal: Kff*(qin[k]-qin_equilibrio), alternativa sostenida que no se atribuye como implementación confirmada de los autores.

Límites de descarga por defecto 0–100 L/min: SUPUESTO, pendiente de calibración. Anti-windup por integración condicional, añadido a esta réplica. Integral inicial cero, sesgo igual al caudal de equilibrio. Mediana causal de 10 muestras, con historial inicial constante. Ruido gaussiano opcional, semilla reproducible; no se agrega por defecto.

La alimentación nominal es 45 L/min. El rebose líquido nominal es configurable y por defecto cero: simplificación hidráulica, no reproducción de una espuma real. Las descargas de equilibrio se obtienen restando los reboses sucesivos a la alimentación.

## Experimento y métricas

Escenario ilustrativo de 600 s: niveles iniciales (30,34,33) cm; consignas (29,33,32) desde 180 s; alimentación 45→50 L/min a 300 s y 50→45 a 450 s. Estas secuencias NO son una digitalización de la Figura 14. Puede reemplazarlas mediante `setpoint_events` y `feed_events`. Los tiempos se aplican en la primera muestra igual o posterior al evento.

Métricas por integración rectangular izquierda: IAE real y filtrado (cm·s), ISE (cm²·s), ITAE (cm·s²), máximo error absoluto (cm), variación total de órdenes (L/min) y tiempo de saturación (s). Solo se integran intervalos avanzados. No se comparan como equivalentes a los IAE experimentales sin datos y protocolos iguales. No se calcula un único tiempo de establecimiento porque hay múltiples eventos.

## Límites de la réplica

No hay datos originales, código de los autores, calibración real de bombas ni secuencia exacta de consignas. El artículo también presenta un modelo autorregulado distinto del integrador de la Tabla 2 y deja ambigua la acción anticipativa. Esta implementación es una reconstrucción trazable, no una validación experimental. La primera celda mantiene su alimentación como entrada externa; el tanque de recirculación no se modela dinámicamente.

## Identificación y validación

`identification.py` incluye regresión lineal para calibración, identificación de ganancia integradora desde una rampa posterior a un escalón (con corrección de deriva previa) y cálculo SIMC para un integrador puro. La ventana de ajuste y el retardo deben obtenerse de los datos. `validate.py` guarda un informe legible, un JSON detallado y el registro de pruebas, y compara pasos de integración de 1, 0.5 y 0.25 s manteniendo la ventana de filtrado de 10 s.

La interfaz HTML consume la API WSGI. Las ecuaciones de planta, control y sintonización permanecen en Python. El JavaScript se limita al formulario, solicitud de resultados, presentación gráfica y exportación.

