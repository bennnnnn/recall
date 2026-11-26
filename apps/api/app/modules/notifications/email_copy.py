"""Transactional email copy: one {subject, text, html} per kind and locale.

Keep copy short and plain-text-friendly. Every app language has its own copy of every
email (``test_every_app_language_has_its_own_email``); English is the source and the
fallback for a locale the app does not offer. ``transactional_email`` renders it.
"""

TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "welcome": {
        "en": {
            "subject": "Welcome to Recall",
            "text": (
                "{greeting}\n\n"
                "Welcome to Recall — your personal AI chat that remembers what "
                "matters to you. Ask it anything, or jot down reminders.\n\n"
                "A few things to try first:\n"
                "  - Tell Recall about yourself so its memory gets useful fast.\n"
                "  - Set your preferred language, tone, and response length in Settings.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>{greeting}</p>"
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
                "{greeting}\n\n"
                "Bienvenido a Recall — tu chat de IA personal que recuerda lo que te "
                "importa. Pregúntale cualquier cosa o anota recordatorios.\n\n"
                "Algunas cosas para empezar:\n"
                "  - Cuéntale a Recall sobre ti para que su memoria sea útil.\n"
                "  - Configura tu idioma, tono y longitud de respuesta en Ajustes.\n\n"
                "Saludos,\nEl equipo de Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
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
                "{greeting}\n\n"
                "Bienvenue sur Recall — votre chat IA personnel qui se souvient de ce "
                "qui compte pour vous. Posez-lui vos questions ou notez vos rappels.\n\n"
                "Quelques idées pour commencer :\n"
                "  - Parlez de vous à Recall pour enrichir sa mémoire.\n"
                "  - Choisissez votre langue, ton et longueur de réponse.\n\n"
                "Cordialement,\nL'équipe Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
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
                "{greeting}\n\n"
                "Bem-vindo ao Recall — seu chat de IA pessoal que lembra do que "
                "importa para você. Pergunte qualquer coisa ou anote lembretes.\n\n"
                "Algumas dicas para começar:\n"
                "  - Conte ao Recall sobre você para enriquecer a memória.\n"
                "  - Defina idioma, tom e tamanho das respostas.\n\n"
                "Abraços,\nEquipe Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
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
                "{greeting}\n\n"
                "Добро пожаловать в Recall — ваш личный ИИ-чат, который запоминает то, "
                "что вам важно. Задавайте любые вопросы или записывайте напоминания.\n\n"
                "С чего начать:\n"
                "  - Расскажите Recall о себе, чтобы память стала полезной.\n"
                "  - Выберите язык, тон и длину ответов в Настройках.\n\n"
                "С уважением,\nКоманда Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
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
                "{greeting}\n\n"
                "Recall'a hoş geldiniz — sizin için önemli olanları hatırlayan kişisel "
                "yapay zeka sohbetiniz. Ona her şeyi sorun veya hatırlatmalar not edin.\n\n"
                "Başlamak için birkaç öneri:\n"
                "  - Recall'a kendinizden bahsedin ki belleği yararlı olsun.\n"
                "  - Ayarlar'da dil, ton ve yanıt uzunluğunu seçin.\n\n"
                "Sevgiler,\nRecall ekibi"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p>Recall'a hoş geldiniz — kişisel yapay zeka sohbetiniz.</p>"
                "<p>Başlamak için:</p>"
                "<ul>"
                "<li>Recall'a kendinizden bahsedin.</li>"
                "<li>Dil, ton ve yanıt uzunluğunu ayarlayın.</li>"
                "</ul>"
                "<p>Sevgiler,<br/>Recall ekibi</p>"
            ),
        },
        "am": {
            "subject": "ወደ Recall እንኳን በደህና መጡ",
            "text": (
                "{greeting}\n\n"
                "ወደ Recall እንኳን በደህና መጡ — ለእርስዎ አስፈላጊ የሆነውን የሚያስታውስ የግል AI "
                "ውይይትዎ። ማንኛውንም ነገር ይጠይቁ፣ ወይም አስታዋሾችን ይመዝግቡ።\n\n"
                "ለመጀመር ጥቂት ነገሮች፦\n"
                "  - ትውስታው በፍጥነት እንዲጠቅምዎ ስለራስዎ ለRecall ይንገሩት።\n"
                "  - በቅንብሮች ውስጥ ቋንቋዎን፣ የአነጋገር ቃናውን እና የመልሱን ርዝመት ይምረጡ።\n\n"
                "ከሰላምታ ጋር፣\nየRecall ቡድን"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p>ወደ <strong>Recall</strong> እንኳን በደህና መጡ — ለእርስዎ አስፈላጊ የሆነውን "
                "የሚያስታውስ የግል AI ውይይትዎ።</p>"
                "<p>ለመጀመር፦</p>"
                "<ul>"
                "<li>ስለራስዎ ለRecall ይንገሩት።</li>"
                "<li>በቅንብሮች ውስጥ ቋንቋ፣ ቃና እና ርዝመት ይምረጡ።</li>"
                "</ul>"
                "<p>ከሰላምታ ጋር፣<br/>የRecall ቡድን</p>"
            ),
        },
        "hi": {
            "subject": "Recall में आपका स्वागत है",
            "text": (
                "{greeting}\n\n"
                "Recall में आपका स्वागत है — आपकी निजी AI चैट, जो याद रखती है कि आपके लिए "
                "क्या मायने रखता है। कुछ भी पूछिए, या रिमाइंडर लिख लीजिए।\n\n"
                "शुरुआत के लिए कुछ बातें:\n"
                "  - Recall को अपने बारे में बताइए, ताकि उसकी याददाश्त जल्दी काम आए।\n"
                "  - सेटिंग्स में अपनी भाषा, लहजा और जवाब की लंबाई चुनिए।\n\n"
                "शुभकामनाएँ,\nRecall टीम"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p><strong>Recall</strong> में आपका स्वागत है — आपकी निजी AI चैट, जो याद रखती "
                "है कि आपके लिए क्या मायने रखता है।</p>"
                "<p>शुरुआत के लिए:</p>"
                "<ul>"
                "<li>Recall को अपने बारे में बताइए।</li>"
                "<li>सेटिंग्स में भाषा, लहजा और जवाब की लंबाई चुनिए।</li>"
                "</ul>"
                "<p>शुभकामनाएँ,<br/>Recall टीम</p>"
            ),
        },
    },
    "receipt": {
        "en": {
            "subject": "Your Recall receipt",
            "text": (
                "{greeting}\n\n"
                "Thanks for subscribing to Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nYou can review or manage your subscription anytime from Settings "
                "in the app.\n\n"
                "Cheers,\nThe Recall team"
            ),
            "html": (
                "<p>{greeting}</p>"
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
                "{greeting}\n\n"
                "¡Gracias por suscribirte a Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nPuedes gestionar tu suscripción cuando quieras desde Ajustes.\n\n"
                "Saludos,\nEl equipo de Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p>¡Gracias por suscribirte a <strong>Recall</strong>!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Gestiona tu suscripción desde Ajustes en la app.</p>"
                "<p>Saludos,<br/>El equipo de Recall</p>"
            ),
        },
        "fr": {
            "subject": "Votre reçu Recall",
            "text": (
                "{greeting}\n\n"
                "Merci pour votre abonnement à Recall !\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nGérez votre abonnement à tout moment depuis les Réglages.\n\n"
                "Cordialement,\nL'équipe Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p>Merci pour votre abonnement à <strong>Recall</strong> !</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Gérez votre abonnement depuis les Réglages.</p>"
                "<p>Cordialement,<br/>L'équipe Recall</p>"
            ),
        },
        "pt": {
            "subject": "Seu recibo do Recall",
            "text": (
                "{greeting}\n\n"
                "Obrigado por assinar o Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nGerencie sua assinatura a qualquer momento nos Ajustes.\n\n"
                "Abraços,\nEquipe Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p>Obrigado por assinar o <strong>Recall</strong>!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Gerencie sua assinatura nos Ajustes.</p>"
                "<p>Abraços,<br/>Equipe Recall</p>"
            ),
        },
        "ru": {
            "subject": "Ваш чек Recall",
            "text": (
                "{greeting}\n\n"
                "Спасибо за подписку на Recall!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nУправлять подпиской можно в Настройках приложения.\n\n"
                "С уважением,\nКоманда Recall"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p>Спасибо за подписку на <strong>Recall</strong>!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Управлять подпиской — в Настройках.</p>"
                "<p>С уважением,<br/>Команда Recall</p>"
            ),
        },
        "tr": {
            "subject": "Recall dekontunuz",
            "text": (
                "{greeting}\n\n"
                "Recall'a abone olduğunuz için teşekkürler!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nAboneliğinizi Ayarlar'dan istediğiniz zaman yönetebilirsiniz.\n\n"
                "Sevgiler,\nRecall ekibi"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p><strong>Recall</strong>'a abone olduğunuz için teşekkürler!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>Aboneliğinizi Ayarlar'dan yönetin.</p>"
                "<p>Sevgiler,<br/>Recall ekibi</p>"
            ),
        },
        "am": {
            "subject": "የRecall ደረሰኝዎ",
            "text": (
                "{greeting}\n\n"
                "ለRecall ስለተመዘገቡ እናመሰግናለን!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nምዝገባዎን በመተግበሪያው ቅንብሮች ውስጥ በማንኛውም ጊዜ ማየት ወይም ማስተዳደር "
                "ይችላሉ።\n\n"
                "ከሰላምታ ጋር፣\nየRecall ቡድን"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p>ለ<strong>Recall</strong> ስለተመዘገቡ እናመሰግናለን!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>ምዝገባዎን በመተግበሪያው ቅንብሮች ውስጥ ያስተዳድሩ።</p>"
                "<p>ከሰላምታ ጋር፣<br/>የRecall ቡድን</p>"
            ),
        },
        "hi": {
            "subject": "आपकी Recall रसीद",
            "text": (
                "{greeting}\n\n"
                "Recall की सदस्यता लेने के लिए धन्यवाद!\n\n"
                "{event_line}"
                "{expiration_line}"
                "\nआप ऐप की सेटिंग्स में अपनी सदस्यता कभी भी देख या बदल सकते हैं।\n\n"
                "शुभकामनाएँ,\nRecall टीम"
            ),
            "html": (
                "<p>{greeting}</p>"
                "<p><strong>Recall</strong> की सदस्यता लेने के लिए धन्यवाद!</p>"
                "<p>{event_line_html}{expiration_line_html}</p>"
                "<p>अपनी सदस्यता ऐप की सेटिंग्स में संभालिए।</p>"
                "<p>शुभकामनाएँ,<br/>Recall टीम</p>"
            ),
        },
    },
}


TEMPLATES["todo_reminder"] = {
    "en": {
        "subject": "{title}: {content}",
        "text": ("{greeting}\n\n{title}\n\n{content}\n\nOpen Recall to mark it done.\n\n— Recall"),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Open Recall to mark it done.</p>"
            "<p>— Recall</p>"
        ),
    },
    "es": {
        "subject": "{title}: {content}",
        "text": (
            "{greeting}\n\n{title}\n\n{content}\n\n"
            "Abre Recall para marcarlo como hecho.\n\n"
            "— Recall"
        ),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Abre Recall para marcarlo como hecho.</p>"
            "<p>— Recall</p>"
        ),
    },
    "fr": {
        "subject": "{title}: {content}",
        "text": (
            "{greeting}\n\n{title}\n\n{content}\n\n"
            "Ouvrez Recall pour le marquer comme fait.\n\n"
            "— Recall"
        ),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Ouvrez Recall pour le marquer comme fait.</p>"
            "<p>— Recall</p>"
        ),
    },
    "pt": {
        "subject": "{title}: {content}",
        "text": (
            "{greeting}\n\n{title}\n\n{content}\n\n"
            "Abra o Recall para marcá-lo como concluído.\n\n"
            "— Recall"
        ),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Abra o Recall para marcá-lo como concluído.</p>"
            "<p>— Recall</p>"
        ),
    },
    "ru": {
        "subject": "{title}: {content}",
        "text": (
            "{greeting}\n\n{title}\n\n{content}\n\n"
            "Откройте Recall, чтобы отметить его выполненным.\n\n"
            "— Recall"
        ),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Откройте Recall, чтобы отметить его выполненным.</p>"
            "<p>— Recall</p>"
        ),
    },
    "tr": {
        "subject": "{title}: {content}",
        "text": (
            "{greeting}\n\n{title}\n\n{content}\n\n"
            "Tamamlandı olarak işaretlemek için Recall'u açın.\n\n"
            "— Recall"
        ),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>Tamamlandı olarak işaretlemek için Recall'u açın.</p>"
            "<p>— Recall</p>"
        ),
    },
    "am": {
        "subject": "{title}: {content}",
        "text": (
            "{greeting}\n\n{title}\n\n{content}\n\nእንደተጠናቀቀ ምልክት ለማድረግ Recallን ይክፈቱ።\n\n— Recall"
        ),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>እንደተጠናቀቀ ምልክት ለማድረግ Recallን ይክፈቱ።</p>"
            "<p>— Recall</p>"
        ),
    },
    "hi": {
        "subject": "{title}: {content}",
        "text": (
            "{greeting}\n\n{title}\n\n{content}\n\n"
            "इसे पूरा हुआ चिह्नित करने के लिए Recall खोलिए।\n\n"
            "— Recall"
        ),
        "html": (
            "<p>{greeting}</p>"
            "<p><strong>{title}</strong></p>"
            "<p>{content}</p>"
            "<p>इसे पूरा हुआ चिह्नित करने के लिए Recall खोलिए।</p>"
            "<p>— Recall</p>"
        ),
    },
}


# How every email greets: by name, or without one when the account has none.
GREETINGS: dict[str, dict[str, str]] = {
    "en": {"named": "Hi {name},", "unnamed": "Hi there,"},
    "es": {"named": "Hola {name},", "unnamed": "Hola,"},
    "fr": {"named": "Bonjour {name},", "unnamed": "Bonjour,"},
    "pt": {"named": "Olá {name},", "unnamed": "Olá,"},
    "ru": {"named": "Здравствуйте, {name}!", "unnamed": "Здравствуйте!"},
    "tr": {"named": "Merhaba {name},", "unnamed": "Merhaba,"},
    "am": {"named": "ሰላም {name}፣", "unnamed": "ሰላም፣"},
    "hi": {"named": "नमस्ते {name},", "unnamed": "नमस्ते,"},
}

# A receipt's lines: what happened to the plan (RevenueCat's event), where it was bought, and
# when it renews. An event this table does not know is said generally ("other"), and a store
# it does not know is left out: never RevenueCat's own word for either.
RECEIPT_LINES: dict[str, dict[str, str]] = {
    "en": {
        "INITIAL_PURCHASE": "Your Recall Pro subscription has started.",
        "RENEWAL": "Your Recall Pro subscription has renewed.",
        "UNCANCELLATION": "Your Recall Pro subscription will renew again.",
        "NON_RENEWING_PURCHASE": "Your Recall Pro purchase is complete.",
        "PRODUCT_CHANGE": "Your Recall Pro plan has changed.",
        "SUBSCRIPTION_EXTENDED": "Your Recall Pro subscription has been extended.",
        "other": "Your Recall Pro subscription is active.",
        "store": "Bought through: {store}",
        "renews": "Renews on: {date}",
    },
    "es": {
        "INITIAL_PURCHASE": "Tu suscripción a Recall Pro ha comenzado.",
        "RENEWAL": "Tu suscripción a Recall Pro se ha renovado.",
        "UNCANCELLATION": "Tu suscripción a Recall Pro volverá a renovarse.",
        "NON_RENEWING_PURCHASE": "Tu compra de Recall Pro se ha completado.",
        "PRODUCT_CHANGE": "Tu plan de Recall Pro ha cambiado.",
        "SUBSCRIPTION_EXTENDED": "Tu suscripción a Recall Pro se ha extendido.",
        "other": "Tu suscripción a Recall Pro está activa.",
        "store": "Comprado a través de: {store}",
        "renews": "Se renueva el: {date}",
    },
    "fr": {
        "INITIAL_PURCHASE": "Votre abonnement Recall Pro a commencé.",
        "RENEWAL": "Votre abonnement Recall Pro a été renouvelé.",
        "UNCANCELLATION": "Votre abonnement Recall Pro sera de nouveau renouvelé.",
        "NON_RENEWING_PURCHASE": "Votre achat de Recall Pro est terminé.",
        "PRODUCT_CHANGE": "Votre forfait Recall Pro a changé.",
        "SUBSCRIPTION_EXTENDED": "Votre abonnement Recall Pro a été prolongé.",
        "other": "Votre abonnement Recall Pro est actif.",
        "store": "Acheté via : {store}",
        "renews": "Renouvellement le : {date}",
    },
    "pt": {
        "INITIAL_PURCHASE": "Sua assinatura do Recall Pro começou.",
        "RENEWAL": "Sua assinatura do Recall Pro foi renovada.",
        "UNCANCELLATION": "Sua assinatura do Recall Pro voltará a ser renovada.",
        "NON_RENEWING_PURCHASE": "Sua compra do Recall Pro foi concluída.",
        "PRODUCT_CHANGE": "Seu plano do Recall Pro mudou.",
        "SUBSCRIPTION_EXTENDED": "Sua assinatura do Recall Pro foi estendida.",
        "other": "Sua assinatura do Recall Pro está ativa.",
        "store": "Comprado pela: {store}",
        "renews": "Renova em: {date}",
    },
    "ru": {
        "INITIAL_PURCHASE": "Ваша подписка Recall Pro оформлена.",
        "RENEWAL": "Ваша подписка Recall Pro продлена.",
        "UNCANCELLATION": "Ваша подписка Recall Pro снова будет продлеваться.",
        "NON_RENEWING_PURCHASE": "Покупка Recall Pro завершена.",
        "PRODUCT_CHANGE": "Ваш тариф Recall Pro изменён.",
        "SUBSCRIPTION_EXTENDED": "Срок вашей подписки Recall Pro увеличен.",
        "other": "Ваша подписка Recall Pro активна.",
        "store": "Куплено через: {store}",
        "renews": "Дата продления: {date}",
    },
    "tr": {
        "INITIAL_PURCHASE": "Recall Pro aboneliğiniz başladı.",
        "RENEWAL": "Recall Pro aboneliğiniz yenilendi.",
        "UNCANCELLATION": "Recall Pro aboneliğiniz yeniden yenilenecek.",
        "NON_RENEWING_PURCHASE": "Recall Pro satın alımınız tamamlandı.",
        "PRODUCT_CHANGE": "Recall Pro planınız değişti.",
        "SUBSCRIPTION_EXTENDED": "Recall Pro aboneliğinizin süresi uzatıldı.",
        "other": "Recall Pro aboneliğiniz etkin.",
        "store": "Satın alındığı yer: {store}",
        "renews": "Yenilenme tarihi: {date}",
    },
    "am": {
        "INITIAL_PURCHASE": "የRecall Pro ምዝገባዎ ተጀምሯል።",
        "RENEWAL": "የRecall Pro ምዝገባዎ ታድሷል።",
        "UNCANCELLATION": "የRecall Pro ምዝገባዎ እንደገና ይታደሳል።",
        "NON_RENEWING_PURCHASE": "የRecall Pro ግዢዎ ተጠናቋል።",
        "PRODUCT_CHANGE": "የRecall Pro እቅድዎ ተቀይሯል።",
        "SUBSCRIPTION_EXTENDED": "የRecall Pro ምዝገባዎ ተራዝሟል።",
        "other": "የRecall Pro ምዝገባዎ ንቁ ነው።",
        "store": "የተገዛው በ፦ {store}",
        "renews": "የሚታደስበት ቀን፦ {date}",
    },
    "hi": {
        "INITIAL_PURCHASE": "आपकी Recall Pro सदस्यता शुरू हो गई है।",
        "RENEWAL": "आपकी Recall Pro सदस्यता का नवीनीकरण हो गया है।",
        "UNCANCELLATION": "आपकी Recall Pro सदस्यता फिर से नवीनीकृत होगी।",
        "NON_RENEWING_PURCHASE": "आपकी Recall Pro खरीद पूरी हो गई है।",
        "PRODUCT_CHANGE": "आपका Recall Pro प्लान बदल गया है।",
        "SUBSCRIPTION_EXTENDED": "आपकी Recall Pro सदस्यता बढ़ा दी गई है।",
        "other": "आपकी Recall Pro सदस्यता सक्रिय है।",
        "store": "कहाँ से खरीदी: {store}",
        "renews": "नवीनीकरण की तारीख: {date}",
    },
}

# The store a purchase went through, by RevenueCat's name for it, as the store names itself.
STORE_NAMES: dict[str, str] = {
    "app_store": "App Store",
    "mac_app_store": "Mac App Store",
    "play_store": "Google Play",
    "amazon": "Amazon Appstore",
    "stripe": "Stripe",
}
