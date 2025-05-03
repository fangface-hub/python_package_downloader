# Ayuda

## Uso

1. Inicie `PythonPackageDownloader`

1. Ingrese la información de descarga

    Los elementos de la pantalla son los siguientes:

    | Elemento de pantalla | Descripción |
    | ---- | ---- |
    | Método de descarga | Obligatorio<br>Si PyPISimple y requests no están instalados, se usará pip forzosamente.<br>Usar pip: Descargar paquetes usando pip download con el pip del entorno de descarga<br>No usar pip: Descargar paquetes usando HTTP |
    | Seleccionar SO | Seleccione Windows, Linux o macOS |
    | Versión de Python | Obligatorio, selección múltiple permitida<br>Seleccione la versión de Python de destino |
    | Lista de paquetes | Obligatorio<br>Especifique la ruta a la lista de paquetes (archivo de texto)<br>El formato es el mismo que `requirements.txt` usado en `pip install -r requirements.txt` |
    | Destino de descarga | Obligatorio<br>Especifique la carpeta de destino de descarga.<br>Por defecto es la carpeta downloads en la ubicación del script |
    | Ruta de pip | Obligatorio cuando se usa pip<br>Busca pip en el entorno de descarga y lo muestra inicialmente |
    | Usar proxy<br>Usuario ~ Puerto | Opcional<br>Ingrese si usa un proxy |
    | Incluir formato fuente | Opcional<br>Si la descarga falla, intente descargar el formato tar.gz |  
    | Descargar dependencias | Verifica las dependencias de los paquetes descargados y descarga recursivamente<br>Tenga en cuenta que el tiempo de procesamiento puede aumentar según el paquete |

    > Presione el botón "Guardar configuración" para guardar los elementos ingresados

1. Presione el botón "Iniciar descarga"
