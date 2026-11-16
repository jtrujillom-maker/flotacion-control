# Dashboard v2

Interfaz reorganizada para uso como laboratorio de control de procesos.

- Indicadores principales al inicio: IAE total, reducción frente a PI y horizonte.
- Panel de parámetros separado de la vista del proceso y del análisis.
- Banco de celdas con nivel, consigna y caudal del instante seleccionado.
- Línea de tiempo, reproducción de la evolución y retorno al estado final.
- Escenarios rápidos de referencia, perturbación y ruido.
- Gráficos con bandas temporales para eventos, leyendas y comparación por celda.
- Comparación visual del IAE total y tabla con el mejor resultado observado resaltado.
- Aviso de cambios sin simular; exportación deshabilitada hasta recalcular.
- Diseño adaptable, enlace para saltar al contenido, etiquetas de controles y soporte para movimiento reducido.

Los cálculos de planta, PI, feedforward y SIMC siguen ejecutándose en Python. El navegador presenta y recorre las series calculadas. La reproducción es una visualización de la simulación ya resuelta, no adquisición experimental en tiempo real.

## Verificación de navegador

Se comprobó la interfaz local en 1440 × 1000 y 390 × 844, sin desbordamiento horizontal del documento. Se probaron el escenario de perturbación, ruido de 0.08 cm, SIMC, restablecimiento, cambio de instante a 0 y 300 s, retorno al instante final y descarga CSV. El escenario de referencia mantiene IAE total 176.20 cm·s y reducción del 31.1 % frente a PI.

Se corrigió el conflicto entre el identificador del botón de restablecimiento y el método nativo `form.reset`. Las pruebas se ejecutaron contra el servidor Python local.

Esta versión no se ha subido a GitHub ni se ha publicado en Render.
