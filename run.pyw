# Rode este arquivo com pythonw para abrir o widget sem janela de terminal.
# Duplo-clique no run.pyw no Explorer deve funcionar direto se Python estiver instalado.
import runpy, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
runpy.run_module("widget", run_name="__main__", alter_sys=True)
