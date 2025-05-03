# 도움말

## 사용 방법

1. `PythonPackageDownloader` 실행

1. 다운로드 정보 입력

    화면 항목은 다음과 같습니다:

    | 화면 항목 | 설명 |
    | ---- | ---- |
    | 다운로드 방법 | 필수 항목<br>PyPISimple과 requests가 설치되지 않은 경우 강제로 pip를 사용합니다.<br>pip 사용: 다운로드 환경의 pip를 사용하여 pip download 실행<br>pip 사용 안 함: HTTP를 사용하여 패키지 다운로드 |
    | OS 선택 | Windows, Linux 또는 macOS 선택 |
    | Python 버전 | 필수 항목, 다중 선택 가능<br>대상 Python 버전 선택 |
    | 패키지 목록 | 필수 항목<br>패키지 목록(텍스트 파일) 경로 지정<br>형식은 `pip install -r requirements.txt`의 `requirements.txt`와 동일 |
    | 다운로드 대상 | 필수 항목<br>다운로드 대상 폴더 지정<br>기본값은 스크립트 위치의 downloads 폴더 |
    | pip 경로 | pip 사용 시 필수 항목<br>다운로드 환경에서 pip를 검색하여 초기 표시 |
    | 프록시 사용<br>사용자 ~ 포트 | 선택 항목<br>프록시를 사용하는 경우 입력 |
    | 소스 형식 포함 | 선택 항목<br>다운로드 실패 시 tar.gz 형식 다운로드 시도 |  
    | 종속성 다운로드 | 다운로드한 패키지의 종속성을 확인하고 재귀적으로 다운로드<br>패키지에 따라 처리 시간이 길어질 수 있으므로 주의 |

    > "설정 저장" 버튼을 눌러 입력 항목 저장

1. "다운로드 시작" 버튼 클릭
