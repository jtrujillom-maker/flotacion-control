# Informe de validación Python

Python 3.14.6. Pruebas: 21; resultado: OK.

## IAE del escenario ilustrativo (cm·s)

| Estrategia | Celda 1 | Celda 2 | Celda 3 |
|---|---:|---:|---:|
| pi | 35.020 | 91.187 | 129.349 |
| pi_ff_literal | 35.015 | 90.645 | 127.260 |
| pi_ff_nominal | 28.910 | 71.818 | 75.472 |

Las tres estrategias completaron 600 s con el modelo empírico. Estos resultados no son datos experimentales del artículo.

El modelo geométrico con las mismas ganancias cruza un límite físico: necesita sintonización propia.

API: pruebas de manejadores en memoria. También pasaron 7 comprobaciones HTTP reales contra http://127.0.0.1:8000.

El informe JSON incluye sensibilidad al paso de integración (1, 0.5 y 0.25 s), conservando la ventana de filtrado de 10 s.

Los puntos de partida SIMC se calculan con la regla de integrador puro; no fuerzan coincidencia con valores finales ajustados por ensayo y error.