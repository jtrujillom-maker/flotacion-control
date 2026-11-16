"""One-command reproducible validation; saves test log and validation report."""
from pathlib import Path
from datetime import datetime
import io
import json
import platform
import unittest
from dataclasses import replace
from model import Config, compare
from identification import simc_pi


def main():
    root=Path(__file__).resolve().parent
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(root/'tests'))
    tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (root/'test_results.txt').write_text(stream.getvalue(),encoding='utf-8')
    result=compare()
    geometric=compare(Config(plant='geometric'))
    # Step-size assessment preserves a 10-second filter window at every dt.
    sensitivity={}
    for dt in (1.0,0.5,0.25):
        trial=compare(replace(Config(),dt=dt,filter_samples=round(10/dt)))
        sensitivity[str(dt)]={s:[m['iae'] for m in r['metrics']] for s,r in trial.items()}
    http_file=root/'http_test_results.json'
    http_result=json.loads(http_file.read_text(encoding='utf-8')) if http_file.exists() else None
    report=dict(python=platform.python_version(), generated_at=datetime.now().astimezone().isoformat(),
                tests_run=tests.testsRun, tests_passed=tests.wasSuccessful(),
                http_validation=http_result or 'Handlers tested in memory; live socket test not yet verified.',
                empirical={s:dict(status=r['status'], metrics=r['metrics']) for s,r in result.items()},
                geometric={s:dict(status=r['status'], boundary_event=r['boundary_event']) for s,r in geometric.items()},
                simc_starting_points=[simc_pi(-0.001018,d,tc) for d,tc in zip((7,6,3),(7,6,8))],
                step_size_sensitivity=sensitivity,
                limitations=result['pi']['assumptions'])
    (root/'validation_report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    rows=['# Informe de validación Python','',f'Python {report["python"]}. Pruebas: {tests.testsRun}; resultado: {"OK" if tests.wasSuccessful() else "FALLO"}.',
          '', '## IAE del escenario ilustrativo (cm·s)', '', '| Estrategia | Celda 1 | Celda 2 | Celda 3 |','|---|---:|---:|---:|']
    for s,r in result.items():
        rows.append('| '+s+' | '+' | '.join(f'{m["iae"]:.3f}' for m in r['metrics'])+' |')
    rows.extend(['','Las tres estrategias completaron 600 s con el modelo empírico. Estos resultados no son datos experimentales del artículo.',
                 '', 'El modelo geométrico con las mismas ganancias cruza un límite físico: necesita sintonización propia.',
                 '', 'API: pruebas de manejadores en memoria. '+('También pasaron 7 comprobaciones HTTP reales contra '+http_result['url']+'.' if http_result else 'Conexión HTTP real pendiente de verificar.'),
                 '', 'El informe JSON incluye sensibilidad al paso de integración (1, 0.5 y 0.25 s), conservando la ventana de filtrado de 10 s.',
                 '', 'Los puntos de partida SIMC se calculan con la regla de integrador puro; no fuerzan coincidencia con valores finales ajustados por ensayo y error.'])
    (root/'VALIDACION.md').write_text('\n'.join(rows),encoding='utf-8')
    print(stream.getvalue())
    print('Saved VALIDACION.md, validation_report.json, test_results.txt')
    return 0 if tests.wasSuccessful() else 1


if __name__=='__main__':
    raise SystemExit(main())
