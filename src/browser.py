import base64
import html
import socket
import ssl

class URL:
    def __init__(self, url):
        # self.를 붙이면 인스턴스 변수가 된다.
        # url은 __init__ 메서드가 끝나면 사라진다

        self.connection_pool = {} # 딕셔너리, {(scheme, host, port): socket}

        if url.startswith("view-source:"):
            self.scheme = "view-source"
            self.innerurl = URL(url[12:])
            return

        # data: 스킴은 ://를 사용하지 않으므로 별도 처리
        if url.startswith("data:"):
            self.scheme = "data"
            self.data = url[5:]
            return

        # splits(s, n) 메서드는 문자열에서 s가 처음 n번 등장한 지점을 기준으로 분할한다.
        self.scheme, url = url.split("://", 1)
        # scheme이 반드시 http여야 한다. 
        # 조건이 참이면 아무 일도 일어나지 않고, 거짓이면 AssertionError가 발생한다.
        assert self.scheme in ["http", "https", "file"]

        if self.scheme == "file":
            # file 스킴은 호스트가 없고 경로만 있다
            # file://path/to/file 형식
            self.host = None
            self.port = None
            self.path = url
        else:
            if "/" not in url:
                url = url + "/"
            self.host, url = url.split("/", 1)
            self.path = "/" + url

            if self.scheme == 'http':
                self.port = 80
            elif self.scheme == 'https':
                self.port = 443



    # 파이썬의 메서드에는 항상 self 매개변수를 작성해야 한다.
    # 웹페이지 다운로드하기
    # 소켓을 통해 다른 컴퓨터와 통신한다
    def request(self):
        if self.scheme == "view-source":
            return self.innerurl.request()

        if self.scheme == "data":
            # data:[mediatype][;base64],<data> 형식
            metadata, content = self.data.split(",", 1)

            # base64 디코딩
            if metadata.endswith(";base64"):
                return base64.b64decode(content).decode("utf8")
            else:
                # html 엔티티 디코딩(&lt; -> <, &gt; -> > 등), 안전하게 인코딩된 문자를 원래 문자로 되돌린다
                return html.unescape(content)

        if self.scheme == "file":
            with open(self.path, "r", encoding="utf8") as f:
                return f.read()
        
        # 1. 연결 풀에서 기존 소켓 찾기
        conn_key = (self.scheme, self.host, self.port)
        s = self.connection_pool.get(conn_key)

        # 2. 없거나 끊어진 경우 새로 연결 (소켓 닫히면 None 반환)
        if s is None:
            # 소켓 생성
            # 소켓이란? 두 컴퓨터 간의 통신을 가능하게 하는 양방향 통신 통로
            # 전화기에 비유 가능
            # (1) 전화기 = 소켓
            # (2) 전화번호 = IP 주소 + 포트 번호
            # (3) 전화 걸기 = connect()
            # (4) 대화하기 = 데이터 송수신
            s = socket.socket(
                family=socket.AF_INET, # 다른 컴퓨터를 찾는 방법을 알려주는 주소 패밀리(address family)
                type=socket.SOCK_STREAM, # 통신 방법을 알려주는 소켓 타입(socket type), 임의의 양의 데이터를 전송할 수 있음, 스트림 소켓 - 연결 기반으로 데이터를 순서대로, 신뢰성 있게 전송
                proto=socket.IPPROTO_TCP # 통신 프로토콜을 알려주는 프로토콜 번호(protocol number), TCP 프로토콜 사용, 신뢰성 있는 연결을 제공, 웹 브라우저가 웹 서버와 통신할 때 사용하는 표준 프로토콜
            )
            if self.scheme == 'https':
                ctx = ssl.create_default_context()
                # server_hostname: 하나의 IP 주소에서 여러 개의 HTTPS 웹사이트를 호스팅할 수 있다. 서버가 올바른 SSL 인증서를 선택하고 인증서 검증 시 호스트명 확인에 사용된다.
                s = ctx.wrap_socket(s, server_hostname=self.host)

            try:
                # 호스트에 연결 - 지정한 호스트와 포트로 TCP 연결 수립
                s.connect((self.host, self.port))
                self.connection_pool[conn_key] = s
            except:
                # 연결 실패 처리
                pass

        request = f"GET {self.path} HTTP/1.1\r\n"
        request += f"Host: {self.host}\r\n"
        # HTTP/1.1에서는 기본적으로 지속 연결(keep-alive)을 사용한다. Connection: close 헤더를 보내면 서버에게 응답 후 연결을 닫으라고 알려준다.
        # 소켓을 매번 닫지 않고 연결 풀에 저장, 같은 호스트로 요청 시 기존 소켓 재사용
        request += "Connection: keep-alive\r\n"
        request += "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36\r\n"
        request += "\r\n"

        # 서버에 요청 전송
        # send: 서버에 전송한 데이터의 바이터 수를 알려준다
        # 마지막에는 반드시 \r\n을 두 번 보내야 한다. 한 번만 보내면 서버의 응답을 끝없이 기다리게 된다.
        # 데이터를 주고받을 때, 비트나 바이트로 이루어진 데이터를 주고받는다.
        # - encode: 텍스트를 바이트 스트림으로 변환
        # - decode: 바이트 스트림을 텍스트로 변환
        # - 파이썬은 텍스트와 바이트를 다른 타입으로 구분한다
        s.send(request.encode("utf8"))

        # 데이터가 도착할 때마다 수집하는 루프 작성
        # 파이썬은 makefile이라는 헬퍼 함수 사용
        # 소켓을 파일처럼 다룰 수 있는 객체로 감싸준다 (서버로부터 받은 모든 바이트가 포함된 파일 형식의 객체 반환)
        # 바이트를 utf8 인코딩을 사용하는 문자열로 변환하라고 지시, 한국에서는 euc-kr과 같은 인코딩의 지원이 필요할 수 있다
        # response 객체는 내부적으로 버퍼를 가지고 있고, readline()을 호출할 때마다
        # (1) 버퍼에서 개행 문자(\r\n)까지 읽어서 반환
        # (2) 내부 포인터를 다음 위치로 이동
        # (3) 버퍼가 비어있으면 소켓에서 더 읽어옴
        # JavaScript next(): Iterator 프로토콜을 따르며, {value, done} 객체 반환
        # Python readline(): 그냥 다음 줄을 문자열로 반환, 끝에 도달하면 빈 문자열 "" 반환, 자바스크립트 ReadableStream의 reader 같은 느낌
        # Carriage Return: 타자기 캐리지(종이를 잡고 있는 부분)를 왼쪽 끝으로 밀어서 되돌림
        # Line Feed: 종이를 한 줄 위로 올림
        response = s.makefile("r", encoding="utf8", newline="\r\n")

        # 첫 번째 줄은 상태
        statusline = response.readline()
        version, status, explanation = statusline.split(" ", 2)

        headers = {}

        while True:
            line = response.readline()
            if line == "\r\n": break
            header, value = line.split(":", 1)
            # 헤더는 대소문자를 구분하지 않기 때문에 소문자로 통일
            # 공백 문자는 중요하지 않으므로 시작과 끝에서 공백 문자를 제거한다
            headers[header.casefold()] = value.strip()

        print('headers: ',headers)

        if headers.get("connection", "").lower() == "close":
            s.close()
            del self.connection_pool[conn_key]

        # Content-Length 기반 읽기
        # Conent-Length 헤더 필수, 서버가 본문 크기를 명시해야 함
        # keep-alive일 때, 같은 소켓으로 여러 요청/응답을 주고 받기 때문에 "끝"이면 명확히 알려야 함
        if "content-length" in headers:
            content_length = int(headers["content-length"])
            body = b"" # 빈 바이트 문자열
            
            while len(body) < content_length:
                chunk = s.recv(min(8192, content_length - len(body)))
                if not chunk: # 연결 끊김
                    s.close()
                    del self.connection_pool[conn_key]
                    break
                body += chunk
            # 바이트→문자열, 깨진 문자는 �로 대체
            body = body.decode("utf8", "replace")

        # Transfer-Encoding: chunked 처리
        # 크기를 모를 때 청크 단위로 전송
        elif headers.get("transfer-encoding") == "chunked":
            body = ""
            while True:
                # 청크 크기 읽기
                size_line = read_until_crlf(s)
                # 16진수 문자열을 10진수로 변환
                chunk_size = int(size_line, 16)
                if chunk_size == 0:
                    break
                # 청크 데이터 읽기
                chunk_data = s.recv(chunk_size)
                body += chunk_data.decode("utf8", "replace")
                # CRLF 읽기
                s.recv(2)
        # 둘 다 아닌 경우 (HTTP/1.0 등)
        # HTTP/1.0에서는 keep-alive를 사용하지 않는다. 기본적으로 Connection: close, 매 요청마다 새로운 연결을 맺어야 한다.
        else:
            body = response.read()
            s.close()
            if conn_key in self.connection_pool:
                del self.connection_pool[conn_key]

        # 압축 + 데이터를 쪼개서(chunked) 전송
        assert "transfer-encoding" not in headers
        # 서버는 Content-Encoding 헤더를 사용해 압축을 진행한다. 페이지 로드가 빨라질 수 있다.
        # 브라우저는 자신이 지원하는 압축 알고리즘을 알려주기 위해 Accept-Encoding 헤더를 전송한다.
        assert "content-encoding" not in headers

        return body

def show(body):
    in_tag = False
    
    for c in body:
        if c == "<":
            in_tag = True
        elif c == ">":
            in_tag = False
        elif not in_tag:
            print(c, end="")
        
def load(url):
    body = url.request()
    if hasattr(url, 'scheme') and url.scheme == "view-source":
        print(body) # 태그 등 소스 코드 그대로 보여줌
    else:
        show(body) # textContent 같은 컨텐츠만 보여줌

def read_until_crlf(sock):
    """소켓에서 CRLF까지 읽어서 반환 (CRLF 제외)"""
    line = b""
    while True:
        byte = sock.recv(1)
        if not byte:
            break
        line += byte
        if line.endswith(b"\r\n"):
            # CRLF 제거하고 문자열로 반환
            return line[:-2].decode("utf8")
    return line.decode("utf8")

# 스크립트 실행 시, 실행
if __name__ == "__main__":
    import sys
    load(URL(sys.argv[1]))