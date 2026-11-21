"""Transactional email copy: one {subject, text, html} per kind and locale.

Keep copy short and plain-text-friendly. English is the source and the
fallback for any locale without its own entry, so adding a locale is a
data-only change here. ``transactional_email`` renders it.
"""

TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "welcome": {
        "en": {
            "subject": "Welcome to Recall",
            "text": (
                "Hi {name},\n\n"
                "Welcome to Recall — your personal AI chat that remembers what "
                "matters to you. Ask it anything, or jot down reminders.\n\n"
                "A few things to try first:\n"
                "  - Tell Recall about yourself so its memory gets useful fast.\n"
                "  - Set your preferred language, tone, and response length in Settings.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>Hi {name},</p>"
                "<p>Welcome to <strong>Recall</strong> — your personal AI chat that "
                "remembers what matters to you. Ask it anything, or jot down reminders.</p>"
                "<p>A few things to try first:</p>"
                "<ul>"
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
                "  - Parlez de vous à Recall pour enrichir sa mémoire.\n"
                "  - Choisissez votre langue, ton et longueur de réponse.\n\n"
                "Cordialement,\nL'équipe Recall"
            ),
            "html": (
                "<p>Bonjour {name},</p>"
                "<p>Bienvenue sur <strong>Recall</strong> — votre chat IA personnel.</p>"
                "<p>Pour commencer :</p>"
                "<ul>"
                "<li>Parlez de vous à Recall.</li>"
                "<li>Choisissez langue, ton et longueur.</li>"
                "</ul>"
                "<p>Cordialement,<br/>L'équipe Recall</p>"
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
                "  - Conte ao Recall sobre você para enriquecer a memória.\n"
                "  - Defina idioma, tom e tamanho das respostas.\n\n"
                "Abraços,\nEquipe Recall"
            ),
            "html": (
                "<p>Olá {name},</p>"
                "<p>Bem-vindo ao <strong>Recall</strong> — seu chat de IA pessoal.</p>"
                "<p>Para começar:</p>"
                "<ul>"
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
                "  - Расскажите Recall о себе, чтобы память стала полезной.\n"
                "  - Выберите язык, тон и длину ответов в Настройках.\n\n"
                "С уважением,\nКоманда Recall"
            ),
            "html": (
                "<p>Здравствуйте, {name}!</p>"
                "<p>Добро пожаловать в <strong>Recall</strong> — ваш личный ИИ-чат.</p>"
                "<p>С чего начать:</p>"
                "<ul>"
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
                "  - Recall'a kendinizden bahsedin ki belleği yararlı olsun.\n"
                "  - Ayarlar'da dil, ton ve yanıt uzunluğunu seçin.\n\n"
                "Sevgiler,\nRecall ekibi"
            ),
            "html": (
                "<p>Merhaba {name},</p>"
                "<p>Recall'a hoş geldiniz — kişisel yapay zeka sohbetiniz.</p>"
                "<p>Başlamak için:</p>"
                "<ul>"
                "<li>Recall'a kendinizden bahsedin.</li>"
                "<li>Dil, ton ve yanıt uzunluğunu ayarlayın.</li>"
                "</ul>"
                "<p>Sevgiler,<br/>Recall ekibi</p>"
            ),
        },
    },
    "receipt": {
        "en": {
            "subject": "Your Recall receipt",
            "text": (
                "Hi {name},\n\n"
                "Thanks for subscribing to Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nYou can review or manage your subscription anytime from Settings "
                "in the app.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>Hi {name},</p>"
                "<p>Thanks for subscribing to <strong>Recall</strong>!</p>"
                "<p>"
                "{event_line_html}"
                "{expiration_line_html}"
                "</p>"
                "<p>You can review or manage your subscription anytime from Settings "
                "in the app.</p>"
                "<p>Cheers,<br/>The Recall team</p>"
            ),
        },
        "es": {
            "subject": "Tu recibo de Recall",
            "text": (
                "Hola {name},\n\n"
                "¡Gracias por suscribirte a Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nPuedes gestionar tu suscripción cuando quieras desde Ajustes.\n\n"
                "Saludos,\nEl equipo de Recall"
            ),
            "html": (
                "<p>Hola {name},</p>"
                "<p>¡Gracias por suscribirte a <strong>Recall</strong>!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Gestiona tu suscripción desde Ajustes en la app.</p>"
                "<p>Saludos,<br/>El equipo de Recall</p>"
            ),
        },
        "fr": {
            "subject": "Votre reçu Recall",
            "text": (
                "Bonjour {name},\n\n"
                "Merci pour votre abonnement à Recall !\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nGérez votre abonnement à tout moment depuis les Réglages.\n\n"
                "Cordialement,\nL'équipe Recall"
            ),
            "html": (
                "<p>Bonjour {name},</p>"
                "<p>Merci pour votre abonnement à <strong>Recall</strong> !</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Gérez votre abonnement depuis les Réglages.</p>"
                "<p>Cordialement,<br/>L'équipe Recall</p>"
            ),
        },
        "pt": {
            "subject": "Seu recibo do Recall",
            "text": (
                "Olá {name},\n\n"
                "Obrigado por assinar o Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nGerencie sua assinatura a qualquer momento nos Ajustes.\n\n"
                "Abraços,\nEquipe Recall"
            ),
            "html": (
                "<p>Olá {name},</p>"
                "<p>Obrigado por assinar o <strong>Recall</strong>!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Gerencie sua assinatura nos Ajustes.</p>"
                "<p>Abraços,<br/>Equipe Recall</p>"
            ),
        },
        "ru": {
            "subject": "Ваш чек Recall",
            "text": (
                "Здравствуйте, {name}!\n\n"
                "Спасибо за подписку на Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nУправлять подпиской можно в Настройках приложения.\n\n"
                "С уважением,\nКоманда Recall"
            ),
            "html": (
                "<p>Здравствуйте, {name}!</p>"
                "<p>Спасибо за подписку на <strong>Recall</strong>!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Управлять подпиской — в Настройках.</p>"
                "<p>С уважением,<br/>Команда Recall</p>"
            ),
        },
        "tr": {
            "subject": "Recall dekontunuz",
            "text": (
                "Merhaba {name},\n\n"
                "Recall'a abone olduğunuz için teşekkürler!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nAboneliğinizi Ayarlar'dan istediğiniz zaman yönetebilirsiniz.\n\n"
                "Sevgiler,\nRecall ekibi"
            ),
            "html": (
                "<p>Merhaba {name},</p>"
                "<p><strong>Recall</strong>'a abone olduğunuz için teşekkürler!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Aboneliğinizi Ayarlar'dan yönetin.</p>"
                "<p>Sevgiler,<br/>Recall ekibi</p>"
            ),
        },
    },
}


TEMPLATES["todo_reminder"] = {
    "en": {
        "subject": "{title}: {content}",
        "text": ("Hi {name},\n\n{title}\n\n{content}\n\nOpen Recall to mark it done.\n\n— Recall"),
        "html": (
            "<p>Hi {name},</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Open Recall to mark it done.</p>"
            "<p>— Recall</p>"
        ),
    },
}
