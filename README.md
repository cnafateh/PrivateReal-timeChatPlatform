# 💬 Private Real‑time Chat Platform

A secure, real‑time private messaging platform built with **Django** and **Django Channels**. Users can search for others by unique username, start private conversations, and exchange messages instantly without page refresh using **WebSocket** technology.

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Django](https://img.shields.io/badge/Django-6.0.5-green.svg)
![Django Channels](https://img.shields.io/badge/Channels-4.2.0-purple.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## ✨ Features

- 🔐 **Secure Authentication** – User registration, login, and session management
- 🔍 **Private User Search** – Find users by unique username (no public user list)
- 💬 **Real‑time Messaging** – WebSocket‑based instant messaging with Django Channels
- 📜 **Message History** – Full conversation history with timestamps (Tehran timezone)
- 📱 **Responsive UI** – Clean, mobile‑friendly interface with pure CSS (no external dependencies)
- 🐳 **Dockerized** – One‑command deployment with Docker
- ⚡ **ASGI Architecture** – Handles both synchronous and asynchronous requests

---

## 🛠 Tech Stack

| Category       | Technology                                      |
|----------------|-------------------------------------------------|
| **Backend**    | Python 3.13, Django 6.0.5, Django Channels 4.2 |
| **Real‑time**  | WebSocket, ASGI, Daphne                        |
| **Database**   | SQLite (upgradeable to PostgreSQL)             |
| **Frontend**   | HTML5, CSS3 (Responsive), Vanilla JavaScript   |
| **Container**  | Docker, Docker Compose                          |
| **Version**    | Git, GitHub                                     |

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.13+
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/private-chat-django.git
cd private-chat-django

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Run with Daphne (ASGI server)
daphne -b 0.0.0.0 -p 8000 chatapp_project.asgi:application