# 💬 Pulse — Real-Time Messaging Platform

**Pulse** is a modern real-time private messaging application built with Django, Django Channels, WebSockets, Redis, and PostgreSQL.

Users can discover each other by username, start private conversations, and exchange messages instantly without refreshing the page.

The project is fully containerized and deployed in production with Docker, Daphne, PostgreSQL, Redis, HTTPS/WSS, and Nginx Proxy Manager.

🌐 **Live Demo:** https://chat.sinafateh.ir

---

## ✨ Features

- 🔐 **User Authentication** — Registration, login, logout, and session-based authentication
- 🔍 **User Discovery** — Search for users by their unique username
- 💬 **Private Conversations** — Start one-to-one conversations between registered users
- ⚡ **Real-Time Messaging** — Instant message delivery using WebSockets and Django Channels
- 🗄️ **Persistent Message History** — Conversations and messages stored in PostgreSQL
- 🔴 **Redis Channel Layer** — Redis-backed communication for Django Channels
- 📱 **Responsive Interface** — Modern UI designed for desktop and mobile devices
- 🌙 **Modern Dark UI** — Custom messaging interface built with HTML, CSS, and Vanilla JavaScript
- 🎮 **Interactive 404 Page** — Custom error page with a small interactive mini-game
- 🐳 **Dockerized Deployment** — Application and Redis services managed with Docker Compose
- 🔒 **Production HTTPS/WSS** — Secure HTTP and WebSocket connections behind a reverse proxy
- ⚙️ **Automated Docker Builds** — GitHub Actions automatically builds and publishes production images to GitHub Container Registry

---

## 🛠 Tech Stack

| Category | Technology |
| --- | --- |
| **Backend** | Python, Django |
| **Real-Time** | Django Channels, WebSocket |
| **ASGI Server** | Daphne |
| **Database** | PostgreSQL |
| **Channel Layer** | Redis |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Containerization** | Docker, Docker Compose |
| **Reverse Proxy** | Nginx Proxy Manager |
| **CI** | GitHub Actions |
| **Container Registry** | GitHub Container Registry (GHCR) |
| **Production Protocols** | HTTPS, WSS |
| **Version Control** | Git, GitHub |

---

## 🏗 Architecture

Pulse uses Django's ASGI architecture to support both regular HTTP requests and persistent WebSocket connections.

```text
                         Internet
                            │
                       HTTPS / WSS
                            │
                            ▼
                  Nginx Proxy Manager
                            │
                            ▼
                    Django + Daphne
                       /         \
                      /           \
                     ▼             ▼
               PostgreSQL        Redis
                Messages       Channel Layer
                Users
                Conversations
```

### Request Flow

Regular application requests:

```text
Browser
   │
 HTTPS
   ▼
Reverse Proxy
   │
   ▼
Daphne
   │
   ▼
Django
   │
   ▼
PostgreSQL
```

Real-time messages:

```text
Browser
   │
   WSS
   ▼
Reverse Proxy
   │
   ▼
Daphne
   │
   ▼
Django Channels
   │
   ▼
Redis Channel Layer
```

This allows Pulse to handle traditional Django requests and real-time WebSocket connections within the same application.

---

## 🐳 Docker Architecture

The production application runs as separate Docker services:

```text
┌─────────────────────────────┐
│        Reverse Proxy        │
│    Nginx Proxy Manager      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│            Pulse            │
│      Django + Daphne        │
│          Port 8000          │
└──────────┬──────────┬───────┘
           │          │
           ▼          ▼
     PostgreSQL     Redis
      Database    Channel Layer
```

PostgreSQL and the application communicate through a private Docker network, while Redis is isolated inside the application's internal network.

---

## 🚀 Local Development

### Prerequisites

Make sure you have installed:

- Python
- Git
- Docker and Docker Compose (recommended)

Clone the repository:

```bash
git clone https://github.com/cnafateh/PrivateReal-timeChatPlatform.git
cd PrivateReal-timeChatPlatform
```

---

## ⚙️ Environment Variables

Create a `.env` file in the project root.

Example:

```env
DEBUG=True

DJANGO_SECRET_KEY=your-development-secret-key

ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000

TIME_ZONE=Asia/Tehran

DB_HOST=localhost
DB_PORT=5432
DB_NAME=chatapp_db
DB_USER=chatapp_user
DB_PASSWORD=your-database-password

REDIS_HOST=localhost
REDIS_PORT=6379
```

> Never commit production secrets or your real `.env` file to the repository.

---

## 💻 Running Locally

Create a virtual environment:

```bash
python -m venv venv
```

Activate it.

### Linux / macOS

```bash
source venv/bin/activate
```

### Windows

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply database migrations:

```bash
python manage.py migrate
```

Optionally create an administrator:

```bash
python manage.py createsuperuser
```

Start the ASGI server:

```bash
daphne -b 0.0.0.0 -p 8000 chatapp_project.asgi:application
```

Then open:

```text
http://127.0.0.1:8000
```

> PostgreSQL and Redis must be available and configured through the environment variables when using the production-style configuration.

---

## 📦 Production Deployment

The production version is distributed as a Docker image through GitHub Container Registry:

```text
ghcr.io/cnafateh/chatapp:latest
```

The application can be pulled with:

```bash
docker pull ghcr.io/cnafateh/chatapp:latest
```

The production stack uses:

- Django
- Daphne
- PostgreSQL
- Redis
- Docker
- Nginx Proxy Manager
- HTTPS/WSS

Sensitive configuration such as database credentials and Django secrets is provided through environment variables and is not stored in the repository.

---

## ⚡ CI Pipeline

Every push to the `main` branch triggers GitHub Actions.

The workflow:

```text
Push to main
      │
      ▼
GitHub Actions
      │
      ├── Checkout source
      │
      ├── Build Docker image
      │
      └── Publish image
              │
              ▼
     GitHub Container Registry
              │
              ▼
     ghcr.io/cnafateh/chatapp
```

This keeps the production Docker image synchronized with the latest version of the main branch.

---

## 🔐 Security

Pulse uses several production-oriented security practices:

- Django session-based authentication
- Private user-to-user conversations
- Environment-based secret management
- HTTPS for standard requests
- WSS for encrypted WebSocket connections
- PostgreSQL credentials stored outside the source code
- Redis isolated inside the Docker network
- Production mode with `DEBUG=False`
- Django trusted-host and CSRF configuration

---

## 📂 Project Structure

```text
PrivateReal-timeChatPlatform/
│
├── chat/
│   ├── migrations/
│   ├── consumers.py
│   ├── models.py
│   ├── routing.py
│   ├── urls.py
│   └── views.py
│
├── chatapp_project/
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── static/
│   ├── css/
│   ├── images/
│   └── js/
│
├── templates/
│   ├── chat/
│   └── 404.html
│
├── .github/
│   └── workflows/
│
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── manage.py
├── requirements.txt
└── README.md
```

---

## 🌐 Live Application

Pulse is currently deployed and available at:

**https://chat.sinafateh.ir**

The production environment runs behind HTTPS and uses secure WebSocket (`wss://`) connections for real-time messaging.

---

## 👨‍💻 Author

**Sina Fateh**

Backend / Python Developer

GitHub: https://github.com/cnafateh

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.