"""Transactional email content + dispatch (welcome, purchase receipts).

Templates are locale-aware via ``user.locale``. English is the source and the
fallback for any locale without a dedicated translation; the structure makes
adding more locales a data-only change. All dispatch goes through
``email_gateway.send_email`` and is best-effort.
"""

from __future__ import annotations

import html as html_lib
import logging
from typing import Any

from app.core.config import Settings
from app.gateways import email_gateway
from app.models.orm import User
from app.services import locale as locale_service

logger = logging.getLogger(__name__)

# Locale codes supported by the mobile app (mirrors services/locale.py).
_SUPPORTED_LOCALES = frozenset(locale_service.LOCALE_NAMES.keys())


def _locale_for(user: User) -> str:
    code = locale_service.normalize_locale_code(getattr(user, "locale", None))
    return code if code in _SUPPORTED_LOCALES else "en"


def _display_name(user: User) -> str:
    name = (user.name or "").strip()
    return name if name else "there"


# ── templates ───────────────────────────────────────────────────────────────
# Each entry: {subject, text, html}. Keep copy short and plain-text-friendly.
# Only `en` is authored; other supported locales fall back to `en` for now —
# adding a locale is a matter of adding a key here, no code change needed.

_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "welcome": {
        "en": {
            "subject": "Welcome to Recall",
            "text": (
                "Hi {name},\n\n"
                "Welcome to Recall — your personal AI chat that remembers what "
                "matters to you. Ask it anything, jot down reminders, or start a "
                "learning project.\n\n"
                "A few things to try first:\n"
                "  - Connect your calendar or Gmail in Settings to surface events "
                "and email reminders.\n"
                "  - Tell Recall about yourself so its memory gets useful fast.\n"
                "  - Set your preferred language, tone, and response length in Settings.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>Hi {name},</p>"
                "<p>Welcome to <strong>Recall</strong> — your personal AI chat that "
                "remembers what matters to you. Ask it anything, jot down reminders, "
                "or start a learning project.</p>"
                "<p>A few things to try first:</p>"
                "<ul>"
                "<li>Connect your calendar or Gmail in Settings to surface events "
                "and email reminders.</li>"
                "<li>Tell Recall about yourself so its memory gets useful fast.</li>"
                "<li>Set your preferred language, tone, and response length in Settings.</li>"
                "</ul>"
                "<p>Cheers,<br/>The Recall team</p>"
            ),
        },
        "es": {
            "subject": "Bienvenido a Recall",
            "text": (
                "Hola {name},\n\n"
                "Bienvenido a Recall — tu chat de IA personal que recuerda lo que te "
                "importa. Pregúntale cualquier cosa, anota recordatorios o inicia un "
                "proyecto de aprendizaje.\n\n"
                "Algunas cosas para empezar:\n"
                "  - Conecta tu calendario o Gmail en Ajustes para ver eventos y "
                "recordatorios.\n"
                "  - Cuéntale a Recall sobre ti para que su memoria sea útil.\n"
                "  - Configura tu idioma, tono y longitud de respuesta en Ajustes.\n\n"
                "Saludos,\nEl equipo de Recall"
            ),
            "html": (
                "<p>Hola {name},</p>"
                "<p>Bienvenido a <strong>Recall</strong> — tu chat de IA personal que "
                "recuerda lo que te importa.</p>"
                "<p>Algunas cosas para empezar:</p>"
                "<ul>"
                "<li>Conecta tu calendario o Gmail en Ajustes.</li>"
                "<li>Cuéntale a Recall sobre ti.</li>"
                "<li>Configura idioma, tono y longitud en Ajustes.</li>"
                "</ul>"
                "<p>Saludos,<br/>El equipo de Recall</p>"
            ),
        },
        "fr": {
            "subject": "Bienvenue sur Recall",
            "text": (
                "Bonjour {name},\n\n"
                "Bienvenue sur Recall — votre chat IA personnel qui se souvient de ce "
                "qui compte pour vous. Posez vos questions, notez vos rappels ou "
                "lancez un projet d'apprentissage.\n\n"
                "Quelques idées pour commencer :\n"
                "  - Connectez votre calendrier ou Gmail dans les Réglages.\n"
                "  - Parlez de vous à Recall pour enrichir sa mémoire.\n"
                "  - Choisissez votre langue, ton et longueur de réponse.\n\n"
                "Cordialement,\nL'équipe Recall"
            ),
            "html": (
                "<p>Bonjour {name},</p>"
                "<p>Bienvenue sur <strong>Recall</strong> — votre chat IA personnel.</p>"
                "<p>Pour commencer :</p>"
                "<ul>"
                "<li>Connectez votre calendrier ou Gmail dans les Réglages.</li>"
                "<li>Parlez de vous à Recall.</li>"
                "<li>Choisissez langue, ton et longueur.</li>"
                "</ul>"
                "<p>Cordialement,<br/>L'équipe Recall</p>"
            ),
        },
        "de": {
            "subject": "Willkommen bei Recall",
            "text": (
                "Hallo {name},\n\n"
                "Willkommen bei Recall — deinem persönlichen KI-Chat, der sich an das "
                "erinnert, was dir wichtig ist. Frag alles, notiere Erinnerungen oder "
                "starte ein Lernprojekt.\n\n"
                "Ein paar Tipps zum Start:\n"
                "  - Verbinde Kalender oder Gmail in den Einstellungen.\n"
                "  - Erzähl Recall über dich, damit das Gedächtnis nützlich wird.\n"
                "  - Stelle Sprache, Ton und Antwortlänge in den Einstellungen ein.\n\n"
                "Viele Grüße,\nDas Recall-Team"
            ),
            "html": (
                "<p>Hallo {name},</p>"
                "<p>Willkommen bei <strong>Recall</strong> — deinem persönlichen KI-Chat.</p>"
                "<p>Zum Start:</p>"
                "<ul>"
                "<li>Verbinde Kalender oder Gmail in den Einstellungen.</li>"
                "<li>Erzähl Recall über dich.</li>"
                "<li>Stelle Sprache, Ton und Antwortlänge ein.</li>"
                "</ul>"
                "<p>Viele Grüße,<br/>Das Recall-Team</p>"
            ),
        },
        "it": {
            "subject": "Benvenuto in Recall",
            "text": (
                "Ciao {name},\n\n"
                "Benvenuto in Recall — la tua chat IA personale che ricorda ciò che "
                "ti importa. Chiedi qualsiasi cosa, annota promemoria o inizia un "
                "progetto di apprendimento.\n\n"
                "Qualche idea per iniziare:\n"
                "  - Collega calendario o Gmail in Impostazioni.\n"
                "  - Racconta a Recall di te per arricchire la sua memoria.\n"
                "  - Imposta lingua, tono e lunghezza delle risposte.\n\n"
                "Saluti,\nIl team di Recall"
            ),
            "html": (
                "<p>Ciao {name},</p>"
                "<p>Benvenuto in <strong>Recall</strong> — la tua chat IA personale.</p>"
                "<p>Per iniziare:</p>"
                "<ul>"
                "<li>Collega calendario o Gmail in Impostazioni.</li>"
                "<li>Racconta a Recall di te.</li>"
                "<li>Imposta lingua, tono e lunghezza.</li>"
                "</ul>"
                "<p>Saluti,<br/>Il team di Recall</p>"
            ),
        },
        "pt": {
            "subject": "Bem-vindo ao Recall",
            "text": (
                "Olá {name},\n\n"
                "Bem-vindo ao Recall — seu chat de IA pessoal que lembra do que "
                "importa para você. Pergunte qualquer coisa, anote lembretes ou inicie "
                "um projeto de aprendizado.\n\n"
                "Algumas dicas para começar:\n"
                "  - Conecte calendário ou Gmail em Ajustes.\n"
                "  - Conte ao Recall sobre você para enriquecer a memória.\n"
                "  - Defina idioma, tom e tamanho das respostas.\n\n"
                "Abraços,\nEquipe Recall"
            ),
            "html": (
                "<p>Olá {name},</p>"
                "<p>Bem-vindo ao <strong>Recall</strong> — seu chat de IA pessoal.</p>"
                "<p>Para começar:</p>"
                "<ul>"
                "<li>Conecte calendário ou Gmail em Ajustes.</li>"
                "<li>Conte ao Recall sobre você.</li>"
                "<li>Defina idioma, tom e tamanho.</li>"
                "</ul>"
                "<p>Abraços,<br/>Equipe Recall</p>"
            ),
        },
        "ru": {
            "subject": "Добро пожаловать в Recall",
            "text": (
                "Здравствуйте, {name}!\n\n"
                "Добро пожаловать в Recall — ваш личный ИИ-чат, который запоминает то, "
                "что вам важно. Задавайте вопросы, делайте заметки и напоминания или "
                "начните учебный проект.\n\n"
                "С чего начать:\n"
                "  - Подключите календарь или Gmail в Настройках.\n"
                "  - Расскажите Recall о себе, чтобы память стала полезной.\n"
                "  - Выберите язык, тон и длину ответов в Настройках.\n\n"
                "С уважением,\nКоманда Recall"
            ),
            "html": (
                "<p>Здравствуйте, {name}!</p>"
                "<p>Добро пожаловать в <strong>Recall</strong> — ваш личный ИИ-чат.</p>"
                "<p>С чего начать:</p>"
                "<ul>"
                "<li>Подключите календарь или Gmail в Настройках.</li>"
                "<li>Расскажите Recall о себе.</li>"
                "<li>Выберите язык, тон и длину ответов.</li>"
                "</ul>"
                "<p>С уважением,<br/>Команда Recall</p>"
            ),
        },
        "tr": {
            "subject": "Recall'a hoş geldiniz",
            "text": (
                "Merhaba {name},\n\n"
                "Recall'a hoş geldiniz — sizin için önemli olanları hatırlayan kişisel "
                "yapay zeka sohbetiniz. Soru sorun, hatırlatmalar not edin veya bir "
                "öğrenme projesi başlatın.\n\n"
                "Başlamak için birkaç öneri:\n"
                "  - Ayarlar'da takvim veya Gmail'inizi bağlayın.\n"
                "  - Recall'a kendinizden bahsedin ki belleği yararlı olsun.\n"
                "  - Ayarlar'da dil, ton ve yanıt uzunluğunu seçin.\n\n"
                "Sevgiler,\nRecall ekibi"
            ),
            "html": (
                "<p>Merhaba {name},</p>"
                "<p>Recall'a hoş geldiniz — kişisel yapay zeka sohbetiniz.</p>"
                "<p>Başlamak için:</p>"
                "<ul>"
                "<li>Ayarlar'da takvim veya Gmail'i bağlayın.</li>"
                "<li>Recall'a kendinizden bahsedin.</li>"
                "<li>Dil, ton ve yanıt uzunluğunu ayarlayın.</li>"
                "</ul>"
                "<p>Sevgiler,<br/>Recall ekibi</p>"
            ),
        },
    },
    "receipt": {
        "en": {
            "subject": "Your Recall Pro receipt",
            "text": (
                "Hi {name},\n\n"
                "Thanks for subscribing to Recall Pro!\n\n"
                "Plan: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nYou can review or manage your subscription anytime from Settings "
                "in the app.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>Hi {name},</p>"
                "<p>Thanks for subscribing to <strong>Recall Pro</strong>!</p>"
                "<p>"
                "Plan: Recall Pro<br/>"
                "{event_line_html}"
                "{expiration_line_html}"
                "</p>"
                "<p>You can review or manage your subscription anytime from Settings "
                "in the app.</p>"
                "<p>Cheers,<br/>The Recall team</p>"
            ),
        },
        "es": {
            "subject": "Tu recibo de Recall Pro",
            "text": (
                "Hola {name},\n\n"
                "¡Gracias por suscribirte a Recall Pro!\n\n"
                "Plan: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nPuedes gestionar tu suscripción cuando quieras desde Ajustes.\n\n"
                "Saludos,\nEl equipo de Recall"
            ),
            "html": (
                "<p>Hola {name},</p>"
                "<p>¡Gracias por suscribirte a <strong>Recall Pro</strong>!</p>"
                "<p>Plan: Recall Pro<br/>{event_line_html}{expiration_line_html}</p>"
                "<p>Gestiona tu suscripción desde Ajustes en la app.</p>"
                "<p>Saludos,<br/>El equipo de Recall</p>"
            ),
        },
        "fr": {
            "subject": "Votre reçu Recall Pro",
            "text": (
                "Bonjour {name},\n\n"
                "Merci pour votre abonnement à Recall Pro !\n\n"
                "Plan : Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nGérez votre abonnement à tout moment depuis les Réglages.\n\n"
                "Cordialement,\nL'équipe Recall"
            ),
            "html": (
                "<p>Bonjour {name},</p>"
                "<p>Merci pour votre abonnement à <strong>Recall Pro</strong> !</p>"
                "<p>Plan : Recall Pro<br/>{event_line_html}{expiration_line_html}</p>"
                "<p>Gérez votre abonnement depuis les Réglages.</p>"
                "<p>Cordialement,<br/>L'équipe Recall</p>"
            ),
        },
        "de": {
            "subject": "Deine Recall-Pro-Quittung",
            "text": (
                "Hallo {name},\n\n"
                "Danke für dein Recall Pro-Abo!\n\n"
                "Plan: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nVerwalte dein Abo jederzeit in den Einstellungen.\n\n"
                "Viele Grüße,\nDas Recall-Team"
            ),
            "html": (
                "<p>Hallo {name},</p>"
                "<p>Danke für dein <strong>Recall Pro</strong>-Abo!</p>"
                "<p>Plan: Recall Pro<br/>{event_line_html}{expiration_line_html}</p>"
                "<p>Verwalte dein Abo in den Einstellungen.</p>"
                "<p>Viele Grüße,<br/>Das Recall-Team</p>"
            ),
        },
        "it": {
            "subject": "La tua ricevuta di Recall Pro",
            "text": (
                "Ciao {name},\n\n"
                "Grazie per l'abbonamento a Recall Pro!\n\n"
                "Piano: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nGestisci il tuo abbonamento dalle Impostazioni.\n\n"
                "Saluti,\nIl team di Recall"
            ),
            "html": (
                "<p>Ciao {name},</p>"
                "<p>Grazie per l'abbonamento a <strong>Recall Pro</strong>!</p>"
                "<p>Piano: Recall Pro<br/>{event_line_html}{expiration_line_html}</p>"
                "<p>Gestisci l'abbonamento dalle Impostazioni.</p>"
                "<p>Saluti,<br/>Il team di Recall</p>"
            ),
        },
        "pt": {
            "subject": "Seu recibo do Recall Pro",
            "text": (
                "Olá {name},\n\n"
                "Obrigado por assinar o Recall Pro!\n\n"
                "Plano: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nGerencie sua assinatura a qualquer momento nos Ajustes.\n\n"
                "Abraços,\nEquipe Recall"
            ),
            "html": (
                "<p>Olá {name},</p>"
                "<p>Obrigado por assinar o <strong>Recall Pro</strong>!</p>"
                "<p>Plano: Recall Pro<br/>{event_line_html}{expiration_line_html}</p>"
                "<p>Gerencie sua assinatura nos Ajustes.</p>"
                "<p>Abraços,<br/>Equipe Recall</p>"
            ),
        },
        "ru": {
            "subject": "Ваш чек Recall Pro",
            "text": (
                "Здравствуйте, {name}!\n\n"
                "Спасибо за подписку на Recall Pro!\n\n"
                "План: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nУправлять подпиской можно в Настройках приложения.\n\n"
                "С уважением,\nКоманда Recall"
            ),
            "html": (
                "<p>Здравствуйте, {name}!</p>"
                "<p>Спасибо за подписку на <strong>Recall Pro</strong>!</p>"
                "<p>План: Recall Pro<br/>{event_line_html}{expiration_line_html}</p>"
                "<p>Управлять подпиской — в Настройках.</p>"
                "<p>С уважением,<br/>Команда Recall</p>"
            ),
        },
        "tr": {
            "subject": "Recall Pro dekontunuz",
            "text": (
                "Merhaba {name},\n\n"
                "Recall Pro'ya abone olduğunuz için teşekkürler!\n\n"
                "Plan: Recall Pro\n"
                "{event_line}"
                "{expiration_line}"
                "\nAboneliğinizi Ayarlar'dan istediğiniz zaman yönetebilirsiniz.\n\n"
                "Sevgiler,\nRecall ekibi"
            ),
            "html": (
                "<p>Merhaba {name},</p>"
                "<p><strong>Recall Pro</strong>'ya abone olduğunuz için teşekkürler!</p>"
                "<p>Plan: Recall Pro<br/>{event_line_html}{expiration_line_html}</p>"
                "<p>Aboneliğinizi Ayarlar'dan yönetin.</p>"
                "<p>Sevgiler,<br/>Recall ekibi</p>"
            ),
        },
    },
}


_TEMPLATES["todo_reminder"] = {
    "en": {
        "subject": "{title}: {content}",
        "text": (
            "Hi {name},\n\n"
            "{title}\n\n"
            "{content}\n\n"
            "Open Recall to mark it done or snooze.\n\n"
            "— Recall"
        ),
        "html": (
            "<p>Hi {name},</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Open Recall to mark it done or snooze.</p>"
            "<p>— Recall</p>"
        ),
    },
}

_TEMPLATES["learning_nudge"] = {
    "en": {
        "subject": "Time to learn",
        "text": ("Hi {name},\n\n{body}\n\nOpen Recall to continue.\n\n— Recall"),
        "html": ("<p>Hi {name},</p><p>{body}</p><p>Open Recall to continue.</p><p>— Recall</p>"),
    },
}


def _template(kind: str, locale: str) -> dict[str, str]:
    bundle = _TEMPLATES.get(kind, {})
    return bundle.get(locale) or bundle["en"]


def _render(template: str, **kwargs: Any) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def _esc(value: object) -> str:
    """HTML-escape a value bound for an `html` template variant.

    BUG FIX (was silent): _render() used to interpolate values into the html
    template exactly like the text one — no escaping. name/title/content/body
    are all user-entered (todo content, learning project titles, display
    name) and event_type/store/product_id come from RevenueCat webhook data.
    Unescaped, a todo titled e.g. `<img src=x onerror=...>` renders as live
    markup in the recipient's HTML email client. Never call this on values
    going into the `text` variant — plain text doesn't need escaping and
    `&amp;` etc. would just be visual noise.
    """
    return html_lib.escape(str(value))


def _strip_header_chars(value: str) -> str:
    """Defense-in-depth: user content must never reach a Subject line with
    embedded CR/LF. Resend's API takes `subject` as a JSON field rather than
    raw SMTP header text, so classic header injection isn't known-exploitable
    through this specific provider, but this is cheap and provider-independent.
    """
    return value.replace("\r", " ").replace("\n", " ")


def build_welcome(user: User) -> tuple[str, str, str]:
    """Return (subject, html, text) for the welcome email."""
    locale = _locale_for(user)
    tpl = _template("welcome", locale)
    name = _display_name(user)
    return (
        tpl["subject"],
        _render(tpl["html"], name=_esc(name)),
        _render(tpl["text"], name=name),
    )


def build_receipt(
    user: User,
    *,
    event_type: str,
    store: str | None = None,
    product_id: str | None = None,
    expiration: str | None = None,
) -> tuple[str, str, str]:
    """Return (subject, html, text) for a purchase/renewal receipt."""
    locale = _locale_for(user)
    tpl = _template("receipt", locale)
    name = _display_name(user)

    event_line = f"Event: {event_type}\n"
    if store:
        event_line += f"Store: {store}\n"
    if product_id:
        event_line += f"Product: {product_id}\n"
    expiration_line = f"Renews: {expiration}\n" if expiration else ""

    # Built independently from event_line/expiration_line (not derived via
    # str.replace) so each field can be escaped before it's embedded — the
    # text variant must stay unescaped, so the two can't share one fragment.
    event_line_html = f"Event: {_esc(event_type)}<br/>"
    if store:
        event_line_html += f"Store: {_esc(store)}<br/>"
    if product_id:
        event_line_html += f"Product: {_esc(product_id)}<br/>"
    expiration_line_html = f"Renews: {_esc(expiration)}<br/>" if expiration else ""

    return (
        tpl["subject"],
        _render(
            tpl["html"],
            name=_esc(name),
            event_line_html=event_line_html,
            expiration_line_html=expiration_line_html,
        ),
        _render(
            tpl["text"],
            name=name,
            event_line=event_line,
            expiration_line=expiration_line,
        ),
    )


def build_todo_reminder(user: User, *, title: str, content: str) -> tuple[str, str, str]:
    locale = _locale_for(user)
    tpl = _template("todo_reminder", locale)
    name = _display_name(user)
    return (
        _render(tpl["subject"], title=title, content=_strip_header_chars(content)),
        _render(tpl["html"], name=_esc(name), title=_esc(title), content=_esc(content)),
        _render(tpl["text"], name=name, title=title, content=content),
    )


def build_learning_nudge(user: User, *, body: str) -> tuple[str, str, str]:
    locale = _locale_for(user)
    tpl = _template("learning_nudge", locale)
    name = _display_name(user)
    return (
        tpl["subject"],
        _render(tpl["html"], name=_esc(name), body=_esc(body)),
        _render(tpl["text"], name=name, body=body),
    )


# ── dispatch ────────────────────────────────────────────────────────────────


async def send_welcome(settings: Settings, user: User) -> bool:
    subject, html, text = build_welcome(user)
    return await email_gateway.send_email(
        settings, to=user.email, subject=subject, html=html, text=text
    )


async def send_purchase_receipt(
    settings: Settings,
    user: User,
    *,
    event_type: str,
    store: str | None = None,
    product_id: str | None = None,
    expiration: str | None = None,
) -> bool:
    subject, html, text = build_receipt(
        user,
        event_type=event_type,
        store=store,
        product_id=product_id,
        expiration=expiration,
    )
    return await email_gateway.send_email(
        settings, to=user.email, subject=subject, html=html, text=text
    )


async def send_todo_reminder(settings: Settings, user: User, *, title: str, content: str) -> bool:
    subject, html, text = build_todo_reminder(user, title=title, content=content)
    return await email_gateway.send_email(
        settings, to=user.email, subject=subject, html=html, text=text
    )


async def send_learning_nudge(settings: Settings, user: User, *, body: str) -> bool:
    subject, html, text = build_learning_nudge(user, body=body)
    return await email_gateway.send_email(
        settings, to=user.email, subject=subject, html=html, text=text
    )
