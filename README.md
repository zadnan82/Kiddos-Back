# 🎓 Kiddos - AI Educational Content Platform

An AI-powered educational content generation platform that helps parents create personalized learning materials for their children in Arabic, English, French, and German.

## ✨ Features

- 🤖 **AI Content Generation** - Claude 3.5 powered educational content
- 🌍 **Multi-language Support** - Arabic (RTL), English, French, German
- 👨‍👩‍👧‍👦 **Parent-Controlled** - Complete parental oversight and approval
- 💳 **Credit System** - Flexible pay-per-use pricing model
- 🔒 **Privacy-First** - COPPA/GDPR compliant from day 1
- 📊 **Analytics Dashboard** - Track learning progress and usage
- 🎯 **Age-Appropriate** - Content tailored for ages 2-12
- 🔄 **Background Processing** - Non-blocking content generation

## 🏗️ Architecture

### Tech Stack

- **Backend**: FastAPI + Python 3.11
- **Database**: PostgreSQL 15 with encryption
- **Cache**: Redis 7 for sessions and rate limiting
- **AI**: Claude 3.5 Sonnet for content generation
- **Queue**: Celery for background processing
- **Payments**: Stripe integration
- **Containers**: Docker + Docker Compose

### Project Structure

```
kiddos-backend/
├── app/
│   ├── main.py                    # FastAPI app (clean, 50 lines)
│   ├── config.py                  # Environment settings
│   ├── database.py                # Database connections
│   ├── models.py                  # SQLAlchemy models (8 tables)
│   ├── schemas.py                 # Pydantic validation (25+ models)
│   ├── auth.py                    # Database token authentication
│   ├── rate_limiter.py            # Redis rate limiting
│   ├── claude_service.py          # AI content generation
│   ├── worker.py                  # Celery background tasks
│   └── routers/                   # API endpoints (35+ routes)
│       ├── auth.py                # Authentication routes
│       ├── user.py                # User management
│       ├── children.py            # Child profiles
│       ├── content.py             # Content generation
│       ├── credits.py             # Payment system
│       ├── dashboard.py           # Analytics
│       ├── admin.py               # Administration
│       └── system.py              # Health checks
├── requirements.txt               # Python dependencies
├── docker-compose.yml            # Development environment
├── Dockerfile                    # Application container
├── .env.example                  # Environment template
└── setup.sh                     # Quick setup script
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Claude API key (from Anthropic)
- Stripe account (for payments)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd kiddos-backend
chmod +x setup.sh
./setup.sh
```

### 2. Configure Environment

Edit `.env` file with your API keys:

```bash
# Required API Keys
CLAUDE_API_KEY=sk-ant-your-claude-api-key
STRIPE_SECRET_KEY=sk_test_your-stripe-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Access Application

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Task Monitor**: http://localhost:5555

## 📋 API Endpoints

### Authentication

```
POST /auth/register         # User registration
POST /auth/login           # User login
POST /auth/logout          # Logout
POST /auth/logout-all      # Logout all devices
```

### Content Generation

```
POST /content/generate      # Generate AI content
GET  /content/status/{id}   # Check generation status
POST /content/{id}/approve  # Parent approval
POST /content/{id}/regenerate # Regenerate with feedback
GET  /content/history       # Content history
```

### Child Management

```
POST /children             # Create child profile
GET  /children             # List children
PUT  /children/{id}        # Update child
DELETE /children/{id}      # Delete child
```

### Credit System

```
GET  /credits/packages     # Available packages
POST /credits/purchase     # Buy credits
GET  /credits/balance      # Check balance
```

### Dashboard & Analytics

```
GET /dashboard             # Main dashboard
GET /dashboard/analytics   # Usage analytics
GET /dashboard/insights    # Personalized insights
```

## 🔧 Development

### Running Tests

```bash
docker-compose exec api pytest
```

### Database Migrations

```bash
# Create migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
```

### Access Shell

```bash
docker-compose exec api bash
```

## 🌍 Deployment

### Production Environment

1. Set `ENVIRONMENT=production` in `.env`
2. Use production-grade secrets
3. Enable SSL/HTTPS
4. Configure monitoring

### Docker Production

```bash
# Production build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables

Key variables for production:

```bash
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<secure-32-char-key>
ENCRYPTION_KEY=<base64-32-byte-key>
DATABASE_URL=<production-db-url>
CLAUDE_API_KEY=<production-claude-key>
STRIPE_SECRET_KEY=<production-stripe-key>
```

## 🔒 Security Features

- **Database Token Authentication** (no JWT vulnerabilities)
- **Field-level Encryption** for all PII data
- **Rate Limiting** with Redis sliding windows
- **Content Moderation** with AI safety checks
- **CORS Protection** and security headers
- **Input Validation** and sanitization
- **SQL Injection Protection** via SQLAlchemy ORM

## 📊 Monitoring

### Health Checks

```bash
curl http://localhost:8000/health
```

### Task Monitoring

Access Flower at http://localhost:5555 for:

- Active tasks
- Task history
- Worker status
- Queue monitoring

### Database Monitoring

```sql
-- Active sessions
SELECT COUNT(*) FROM user_sessions WHERE is_active = true;

-- Content generation stats
SELECT status, COUNT(*) FROM content_sessions GROUP BY status;

-- Credit usage
SELECT SUM(amount) FROM credit_transactions WHERE transaction_type = 'consumption';
```

## 🎯 Rate Limiting

### User Tiers

- **Free**: 3 content/hour, 10/day
- **Basic**: 10 content/hour, 50/day
- **Family**: 20 content/hour, 150/day

### IP Limits

- Registration: 3 per day per IP
- Login attempts: 5 per 5 minutes

## 💳 Payment Integration

### Stripe Setup

1. Create Stripe account
2. Get API keys from dashboard
3. Set up webhooks for `/webhooks/stripe`
4. Configure products and pricing

### Credit Packages

- **Mini**: 30 credits - $2.99
- **Basic**: 100 credits + 10 bonus - $7.99
- **Family**: 250 credits + 50 bonus - $17.99
- **Bulk**: 500 credits + 150 bonus - $29.99

## 🌐 Internationalization

### Supported Languages

- **Arabic** (ar) - Right-to-left support
- **English** (en) - Default
- **French** (fr) - European market
- **German** (de) - European market

### Cultural Adaptations

- Middle Eastern context for Arabic content
- Educational standards compliance
- Age-appropriate cultural references

## 🔄 Background Tasks

### Celery Workers

- Content generation with Claude AI
- Email notifications
- Credit processing
- Data cleanup and maintenance
- Usage report generation

### Scheduled Tasks

- Session cleanup (hourly)
- Content expiry (every 30 minutes)
- Rate limit cleanup (daily)
- Usage reports (daily)

## 📈 Scaling Considerations

### Performance Optimizations

- Redis caching for frequently accessed data
- Database connection pooling
- Async processing for AI requests
- CDN for static assets (future)

### Horizontal Scaling

- Multiple Celery workers
- Database read replicas
- Redis clustering
- Load balancer (Nginx)

## 🛠️ Troubleshooting

### Common Issues

**API not starting:**

```bash
docker-compose logs api
# Check database connection and Redis availability
```

**Claude API errors:**

```bash
# Verify API key in .env
grep CLAUDE_API_KEY .env
```

**Database connection issues:**

```bash
docker-compose exec db psql -U kiddos_user -d kiddos_db
```

**Redis connection issues:**

```bash
docker-compose exec redis redis-cli ping
```

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📞 Support

For support and questions:

- Create an issue on GitHub
- Check the API documentation at `/docs`
- Review logs with `docker-compose logs`

## 🚀 What's Next?

### Planned Features

- Voice cloning for personalized narration
- Mobile app (React Native)
- Advanced analytics and insights
- Multi-tenant support for schools
- Integration with learning management systems

---

**Built with ❤️ for children's education**
