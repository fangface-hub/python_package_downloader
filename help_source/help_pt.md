# Ajuda

## Uso

1. Inicie o `PythonPackageDownloader`

1. Insira as informações de download

    Os itens da tela são os seguintes:

    | Item da tela | Descrição |
    | ---- | ---- |
    | Método de download | Obrigatório<br>Se PyPISimple e requests não estiverem instalados, o pip será usado forçadamente.<br>Usar pip: Baixar pacotes usando pip download com o pip do ambiente de download<br>Não usar pip: Baixar pacotes usando HTTP |
    | Selecionar SO | Selecione Windows, Linux ou macOS |
    | Versão do Python | Obrigatório, seleção múltipla permitida<br>Selecione a versão do Python de destino |
    | Lista de pacotes | Obrigatório<br>Especifique o caminho para a lista de pacotes (arquivo de texto)<br>O formato é o mesmo que `requirements.txt` usado em `pip install -r requirements.txt` |
    | Destino do download | Obrigatório<br>Especifique a pasta de destino do download.<br>O padrão é a pasta downloads no local do script |
    | Caminho do pip | Obrigatório ao usar pip<br>Procura o pip no ambiente de download e o exibe inicialmente |
    | Usar proxy<br>Usuário ~ Porta | Opcional<br>Insira se estiver usando um proxy |
    | Incluir formato de origem | Opcional<br>Se o download falhar, tente baixar o formato tar.gz |  
    | Baixar dependências | Verifica as dependências dos pacotes baixados e baixa recursivamente<br>Observe que o tempo de processamento pode aumentar dependendo do pacote |

    > Pressione o botão "Salvar configurações" para salvar os itens inseridos

1. Pressione o botão "Iniciar download"
