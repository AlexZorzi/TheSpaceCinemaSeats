# TheSpaceCinema Seat Keeper

> A Telegram bot that automatically maintains cinema seat reservations at TheSpaceCinema by refreshing them periodically.

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)

## Try me
Write me at [@thespacecinemabot](https://t.me/thespacecinemabot)


## Prerequisites

- Docker and Docker Compose
- A Telegram Bot Token (get one from [@BotFather](https://t.me/botfather))

## Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/AlexZorzi/TheSpaceCinemaSeats
cd TheSpaceCinemaSeats

echo "BOT_TOKEN=your_telegram_bot_token_here" > .env

docker-compose up -d

```

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your bot token

# Run the bot
python tg.py
```

## Usage

Start a chat with your bot on Telegram:

| Command | Description |
|---------|-------------|
| `/start` | Show help message |
| `/book` | Start new reservation |
| `/mybookings` | View active bookings |
| `/cancel_booking` | Cancel a booking |
| `/analytics` | View usage statistics |

### CLI Mode

For testing without Telegram:

```bash
python main.py
```

## License

GPL-3.0 License - see [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with TheSpaceCinema's terms of service.

---

**Note**: This is an unofficial tool and is not affiliated with or endorsed by TheSpaceCinema.
