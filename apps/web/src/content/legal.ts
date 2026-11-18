import type { Locale } from '@/i18n/config';

/**
 * The privacy policy, terms of service and "how the score works" page, in English and Russian.
 *
 * The policy and terms are drafts: text in [square brackets] must be filled in, and both need a lawyer's
 * review before launch. Changing what people agree to also means changing POLICY_DATE in
 * apps/api/app/consent.py, which asks everyone to agree again.
 */

/** Rendered in order: paragraphs, then items, then a note. */
export type LegalSection = {
  heading: string;
  paragraphs?: string[];
  items?: string[];
  note?: string;
};
export type LegalDoc = {
  title: string;
  updated: string;
  draftNote?: string;
  intro: string;
  sections: LegalSection[];
};
export type LegalPageId = 'privacy' | 'terms' | 'how-scoring-works';

const DRAFT_EN =
  'Draft for review. Text in [square brackets] is still to be filled in, and this page is not yet legal advice.';
const DRAFT_RU =
  'Черновик для проверки. Текст в [квадратных скобках] ещё нужно заполнить; страница пока не является юридической консультацией.';

const privacyEn: LegalDoc = {
  title: 'Privacy Policy',
  updated: 'Last updated 13 November 2026',
  draftNote: DRAFT_EN,
  intro:
    'CareerFit estimates how well your resume fits a job and region. This policy explains what we collect, why, who helps us, how long we keep it and what you can do about it.',
  sections: [
    {
      heading: 'Who we are',
      paragraphs: [
        'CareerFit is run by [legal name of the operator], [address]. For anything about your data, write to [privacy contact email].',
      ],
    },
    {
      heading: 'What we collect',
      items: [
        'Account: your email address, an account id, and how you sign in.',
        'Documents you add: resumes, cover letters and portfolio links, the text read from them, and the skills, jobs and studies found in that text.',
        'What you ask for: the jobs and regions you check, the scores, reports and plans we produce, and resume lines we rewrite for you.',
        'Your agreement: which version of this policy and the terms you accepted, and when, or when you withdrew it.',
        'Purchases: your plan, its status and renewal date, and which reports you bought. Card details stay with Stripe, Apple or Google; we never see them.',
        'Notifications: if you turn them on, your phone’s notification token and app language.',
        'Technical records: request logs with shortened IP addresses and no resume content, and, if enabled, error reports without request contents, personal details or error messages.',
      ],
      note: 'We don’t ask for your age, gender, ethnicity, religion, health, disability or similar details, and we remove them from resumes before any AI reads them (see below). There is no advertising and no tracking for advertising.',
    },
    {
      heading: 'How we use it',
      items: [
        'To read your resume, compare it with the job market and show your score, report and plan.',
        'To run your account, take payments and unlock what you bought.',
        'To send report-ready notifications you turned on.',
        'To keep the service safe: virus scanning of uploads, limits on how often requests can be made, and fixing errors.',
      ],
    },
    {
      heading: 'How AI reads your resume',
      paragraphs: [
        'Before any AI model sees a resume, we remove the name, contact details, links and lines such as date of birth, gender, nationality, religion, marital status, pronouns, disability, ethnicity and health. Unusual layouts can slip through, so leave out anything you don’t want read.',
        'By default the model runs on CareerFit’s own server, and your resume is not sent to an outside AI company. If we switch to a hosted model, we will ask for your agreement again first. The hosted option we have tested uses OpenRouter to reach a model from Baidu: every request tells OpenRouter to use only providers that don’t collect or train on prompts, OpenRouter doesn’t store prompts, and Baidu may keep them for a period it doesn’t state, on servers in China.',
        'Your resume is never used to train AI models, by us or by any provider we use.',
        'The score itself is plain arithmetic, not AI. See How the score works.',
      ],
    },
    {
      heading: 'Legal bases',
      items: [
        'Providing the service you signed up for (contract): your account, documents, results and purchases.',
        'Your consent: having AI read your resume. You can withdraw it in Settings at any time.',
        'Legitimate interests: security, abuse prevention and fixing errors.',
        'Legal obligations: keeping purchase records for tax.',
      ],
    },
    {
      heading: 'Who helps us',
      paragraphs: [
        'These companies process data for us under contract and only for the purposes above. We don’t sell personal data.',
      ],
      items: [
        'Supabase: database, file storage and sign-in, in [region of the Supabase project].',
        'Stripe: website payments. Apple, Google and RevenueCat: in-app purchases.',
        'Expo, Apple and Google: delivering notifications, which carry fixed text and a report id, never resume content.',
        'Sentry: error reports, with names, emails, request bodies and resume text removed before they are sent.',
        'PostHog: counts of pages visited and actions taken, such as "a resume was uploaded", without cookies and never with resume content.',
        'Oracle Cloud: running our server, including the AI model. Vercel: serving the website.',
        'OpenRouter and Baidu: only if we switch to the hosted AI model, after asking you again.',
        '[Hosting provider for the website and API], and, if enabled, [error reporting provider].',
      ],
    },
    {
      heading: 'How long we keep it',
      items: [
        'Uploaded files and the text read from them: deleted 90 days after upload, unless you choose to keep the file. You can change this on the Documents page.',
        'Skills and history found in a resume, results and reports: until you delete them or your account.',
        'Agreement and purchase records: as long as your account exists, and purchase records as long as tax law requires.',
        'Request logs and error reports: [period set by the hosting and error reporting providers].',
        'When you delete your account, we delete your data from our database and file storage straight away, and ask RevenueCat and Stripe to delete their records of you, except what the law makes us keep.',
        'Encrypted nightly backups, kept to recover from an outage, still hold deleted data for up to 14 days and are then deleted. They are only read to restore the service.',
      ],
    },
    {
      heading: 'How we protect it',
      paragraphs: [
        'Connections use HTTPS. Supabase encrypts the database, backups and files at rest with AES-256. Each person can reach only their own data, uploads are checked for viruses, and requests are rate-limited. No system is perfectly secure; if a breach affects you, we will tell you and the authorities as the law requires.',
      ],
    },
    {
      heading: 'Your rights',
      items: [
        'See and take your data: Settings > Download my data gives you everything we store, with your files.',
        'Delete it: delete single documents, or everything at Settings > Delete my account.',
        'Correct it: upload an updated resume and run a new analysis.',
        'Withdraw your agreement: Settings > Privacy. We then stop reading new resumes for you.',
        'Object or complain: write to [privacy contact email]. You can also complain to the Office of the Privacy Commissioner of Canada or, in the EU and UK, your local data protection authority.',
      ],
    },
    {
      heading: 'Where data is stored',
      paragraphs: [
        'Your data is stored in [region of the Supabase project]. Some of the companies above may process it in other countries, under contracts that protect it. With the hosted AI model, resume text is processed in China.',
      ],
    },
    {
      heading: 'Children',
      paragraphs: [
        'CareerFit is not meant for anyone under 16, and we don’t knowingly collect their data.',
      ],
    },
    {
      heading: 'Changes',
      paragraphs: [
        'If we change this policy in a way that matters, the app shows the new version and asks you to agree before it reads another resume.',
      ],
    },
  ],
};

const privacyRu: LegalDoc = {
  title: 'Политика конфиденциальности',
  updated: 'Обновлено 13 ноября 2026 г.',
  draftNote: DRAFT_RU,
  intro:
    'CareerFit оценивает, насколько ваше резюме подходит для вакансии и региона. Здесь объясняется, что мы собираем, зачем, кто нам помогает, как долго мы храним данные и что вы можете с ними сделать.',
  sections: [
    {
      heading: 'Кто мы',
      paragraphs: [
        'CareerFit управляет [юридическое название оператора], [адрес]. По любым вопросам о ваших данных пишите на [адрес электронной почты для вопросов о конфиденциальности].',
      ],
    },
    {
      heading: 'Что мы собираем',
      items: [
        'Аккаунт: адрес электронной почты, идентификатор аккаунта и способ входа.',
        'Добавленные документы: резюме, сопроводительные письма и ссылки на портфолио, прочитанный из них текст и найденные в нём навыки, места работы и обучение.',
        'Ваши запросы: вакансии и регионы, которые вы проверяете, оценки, отчёты и планы, а также строки резюме, которые мы переписали для вас.',
        'Ваше согласие: какую версию этой политики и условий вы приняли и когда, или когда отозвали согласие.',
        'Покупки: ваш тариф, его статус и дата продления, купленные отчёты. Данные карты остаются у Stripe, Apple или Google; мы их не видим.',
        'Уведомления: если вы их включили, токен уведомлений телефона и язык приложения.',
        'Технические записи: журналы запросов с сокращёнными IP-адресами и без содержимого резюме, а также, если включены, отчёты об ошибках без содержимого запросов, личных данных и текстов ошибок.',
      ],
      note: 'Мы не спрашиваем ваш возраст, пол, национальность, религию, здоровье, инвалидность и подобные сведения и убираем их из резюме до того, как его прочитает ИИ (см. ниже). Рекламы и рекламного отслеживания нет.',
    },
    {
      heading: 'Как мы их используем',
      items: [
        'Чтобы прочитать резюме, сравнить его с рынком труда и показать оценку, отчёт и план.',
        'Чтобы вести ваш аккаунт, принимать оплату и открывать купленное.',
        'Чтобы присылать включённые вами уведомления о готовых отчётах.',
        'Чтобы сервис оставался безопасным: проверка загрузок на вирусы, ограничение частоты запросов и исправление ошибок.',
      ],
    },
    {
      heading: 'Как ИИ читает ваше резюме',
      paragraphs: [
        'Прежде чем резюме увидит модель ИИ, мы убираем имя, контакты, ссылки и строки вроде даты рождения, пола, гражданства, религии, семейного положения, местоимений, инвалидности, национальности и здоровья. При необычной вёрстке что-то может остаться, поэтому не указывайте то, что не хотите показывать.',
        'По умолчанию модель работает на собственном сервере CareerFit, и резюме не передаётся сторонним компаниям, работающим с ИИ. Если мы перейдём на облачную модель, мы сначала снова спросим ваше согласие. Проверенный нами облачный вариант использует OpenRouter для доступа к модели Baidu: каждый запрос требует от OpenRouter использовать только поставщиков, которые не собирают запросы и не обучают на них модели; OpenRouter запросы не хранит, а Baidu может хранить их неопределённый срок на серверах в Китае.',
        'Ваше резюме никогда не используется для обучения моделей ИИ ни нами, ни нашими поставщиками.',
        'Сама оценка считается по формуле, без ИИ. См. «Как считается оценка».',
      ],
    },
    {
      heading: 'Правовые основания',
      items: [
        'Оказание услуги, на которую вы зарегистрировались (договор): аккаунт, документы, результаты и покупки.',
        'Ваше согласие: чтение резюме с помощью ИИ. Его можно отозвать в настройках в любой момент.',
        'Законные интересы: безопасность, защита от злоупотреблений и исправление ошибок.',
        'Требования закона: хранение записей о покупках для налоговых целей.',
      ],
    },
    {
      heading: 'Кто нам помогает',
      paragraphs: [
        'Эти компании обрабатывают данные по нашему поручению по договору и только для целей, указанных выше. Мы не продаём персональные данные.',
      ],
      items: [
        'Supabase: база данных, хранение файлов и вход в аккаунт, в регионе [регион проекта Supabase].',
        'Stripe: оплата на сайте. Apple, Google и RevenueCat: покупки в приложении.',
        'Expo, Apple и Google: доставка уведомлений, в которых только стандартный текст и номер отчёта, без содержимого резюме.',
        'Sentry: отчёты об ошибках, из которых до отправки удаляются имена, адреса почты, тела запросов и текст резюме.',
        'PostHog: подсчёт посещённых страниц и действий, например «загружено резюме», без cookie и без содержимого резюме.',
        'Oracle Cloud: работа нашего сервера, включая модель ИИ. Vercel: работа сайта.',
        'OpenRouter и Baidu: только если мы перейдём на облачную модель ИИ, после повторного согласия.',
        '[Хостинг сайта и API], а также, если включён, [сервис отчётов об ошибках].',
      ],
    },
    {
      heading: 'Как долго мы храним данные',
      items: [
        'Загруженные файлы и прочитанный из них текст удаляются через 90 дней после загрузки, если вы не решили сохранить файл. Это можно изменить на странице «Документы».',
        'Найденные в резюме навыки и опыт, результаты и отчёты хранятся, пока вы не удалите их или аккаунт.',
        'Записи о согласии и покупках хранятся, пока существует аккаунт, а записи о покупках — столько, сколько требует налоговое законодательство.',
        'Журналы запросов и отчёты об ошибках: [срок хранения у хостинга и сервиса отчётов об ошибках].',
        'При удалении аккаунта мы сразу удаляем ваши данные из базы данных и хранилища файлов и просим RevenueCat и Stripe удалить их записи о вас, кроме того, что мы обязаны хранить по закону.',
        'В зашифрованных ночных резервных копиях, которые нужны для восстановления после сбоя, удалённые данные остаются до 14 дней, затем копии удаляются. Их открывают только для восстановления сервиса.',
      ],
    },
    {
      heading: 'Как мы защищаем данные',
      paragraphs: [
        'Соединения идут по HTTPS. Supabase шифрует базу данных, резервные копии и файлы на дисках по AES-256. Каждый видит только свои данные, загрузки проверяются на вирусы, частота запросов ограничена. Абсолютно защищённых систем не бывает; если утечка затронет вас, мы сообщим вам и органам власти, как требует закон.',
      ],
    },
    {
      heading: 'Ваши права',
      items: [
        'Получить свои данные: «Настройки» → «Скачать мои данные» выдаёт всё, что мы храним, вместе с файлами.',
        'Удалить их: удаляйте отдельные документы или всё сразу в «Настройки» → «Удалить аккаунт».',
        'Исправить их: загрузите обновлённое резюме и проведите новый анализ.',
        'Отозвать согласие: «Настройки» → «Конфиденциальность». После этого мы перестанем читать новые резюме.',
        'Возразить или пожаловаться: напишите на [адрес электронной почты для вопросов о конфиденциальности]. Также можно обратиться к Уполномоченному по защите частной жизни Канады, а в ЕС и Великобритании — в местный орган по защите данных.',
      ],
    },
    {
      heading: 'Где хранятся данные',
      paragraphs: [
        'Ваши данные хранятся в регионе [регион проекта Supabase]. Некоторые из перечисленных компаний могут обрабатывать их в других странах по договорам, которые их защищают. При облачной модели ИИ текст резюме обрабатывается в Китае.',
      ],
    },
    {
      heading: 'Дети',
      paragraphs: [
        'CareerFit не предназначен для лиц младше 16 лет, и мы сознательно не собираем их данные.',
      ],
    },
    {
      heading: 'Изменения',
      paragraphs: [
        'Если мы существенно изменим эту политику, приложение покажет новую версию и попросит вашего согласия, прежде чем прочитать следующее резюме.',
      ],
    },
  ],
};

const termsEn: LegalDoc = {
  title: 'Terms of Service',
  updated: 'Last updated 13 November 2026',
  draftNote: DRAFT_EN,
  intro:
    'These terms are the agreement between you and [legal name of the operator] for using CareerFit on the web and on phones.',
  sections: [
    {
      heading: 'The service',
      paragraphs: [
        'CareerFit reads a resume, compares it with public job market data and gives an estimated score, a report and a plan. The score is an estimate to help you prepare. It is not a hiring decision, career or legal advice, or a promise of any job, interview or salary.',
        'AI reads your resume and writes suggestions, and AI can be wrong. Check every suggestion before you use it, and never add a skill or result to your resume that isn’t true.',
      ],
    },
    {
      heading: 'Who can use it',
      paragraphs: [
        'You must be at least 16, and old enough to make this agreement where you live. You are responsible for your account and for keeping your sign-in details safe.',
      ],
    },
    {
      heading: 'Your content',
      paragraphs: [
        'You keep all rights to what you upload. You allow us to store and process it only to provide the service to you, as described in the Privacy Policy. Upload only your own documents, or ones you have permission to use.',
      ],
    },
    {
      heading: 'What you may not do',
      items: [
        'Upload someone else’s resume without their permission, or anything unlawful or harmful, including malware.',
        'Try to get around limits, security or payments, or reach other people’s data.',
        'Copy the service or its data in bulk with scripts, or overload it.',
        'Use the results to make automated decisions about other people.',
      ],
    },
    {
      heading: 'Plans and payments',
      items: [
        'Free: one analysis a calendar month, with the full report and plan.',
        'Pro: CA$4.99 a month, renewing until you cancel. Cancel anytime; Pro lasts until the end of the period you paid for.',
        'Detailed report: CA$2.99 for one result, once.',
        'Website payments go through Stripe; in-app purchases through Apple or Google under their terms. Prices are in Canadian dollars; taxes may apply. Refunds: [refund policy]. App store purchases are refunded by the store.',
      ],
    },
    {
      heading: 'Ending the service',
      paragraphs: [
        'You can delete your account at any time in Settings. We may suspend or close accounts that break these terms. If we stop offering CareerFit, we will give you time to download your data.',
      ],
    },
    {
      heading: 'Liability',
      paragraphs: [
        'CareerFit is provided as it is. To the extent the law allows, we are not liable for decisions you or others make based on a score, or for indirect losses, and our total liability is limited to what you paid us in the 12 months before the claim. Nothing here limits rights you have under consumer protection law.',
      ],
    },
    {
      heading: 'Law and changes',
      paragraphs: [
        'These terms are governed by the laws of [province and country]. If we change them in a way that matters, we will ask you to agree again before you continue. Questions: [support contact email].',
      ],
    },
  ],
};

const termsRu: LegalDoc = {
  title: 'Условия использования',
  updated: 'Обновлено 13 ноября 2026 г.',
  draftNote: DRAFT_RU,
  intro:
    'Эти условия — соглашение между вами и [юридическое название оператора] об использовании CareerFit на сайте и в телефоне.',
  sections: [
    {
      heading: 'Сервис',
      paragraphs: [
        'CareerFit читает резюме, сравнивает его с открытыми данными рынка труда и выдаёт примерную оценку, отчёт и план. Оценка помогает подготовиться. Это не решение о найме, не карьерная или юридическая консультация и не обещание работы, собеседования или зарплаты.',
        'Резюме читает ИИ, он же пишет советы, и ИИ может ошибаться. Проверяйте каждый совет перед использованием и никогда не добавляйте в резюме навыки или результаты, которых у вас нет.',
      ],
    },
    {
      heading: 'Кто может пользоваться',
      paragraphs: [
        'Вам должно быть не меньше 16 лет и достаточно лет, чтобы заключить это соглашение там, где вы живёте. Вы отвечаете за свой аккаунт и за сохранность данных для входа.',
      ],
    },
    {
      heading: 'Ваши материалы',
      paragraphs: [
        'Все права на загруженное остаются у вас. Вы разрешаете нам хранить и обрабатывать это только для оказания вам услуги, как описано в Политике конфиденциальности. Загружайте только свои документы или те, которые вам разрешено использовать.',
      ],
    },
    {
      heading: 'Что запрещено',
      items: [
        'Загружать чужое резюме без разрешения владельца, а также незаконные или вредные материалы, включая вредоносные программы.',
        'Пытаться обойти ограничения, защиту или оплату либо получить доступ к чужим данным.',
        'Массово копировать сервис или его данные скриптами или перегружать его.',
        'Использовать результаты для автоматических решений о других людях.',
      ],
    },
    {
      heading: 'Тарифы и оплата',
      items: [
        'Бесплатный: один анализ в календарный месяц с полным отчётом и планом.',
        'Pro: 4,99 канадского доллара в месяц, продлевается, пока вы не отмените. Отменить можно в любой момент; Pro действует до конца оплаченного периода.',
        'Подробный отчёт: 2,99 канадского доллара за один результат, разово.',
        'Оплата на сайте идёт через Stripe, покупки в приложении — через Apple или Google по их правилам. Цены в канадских долларах, могут добавиться налоги. Возвраты: [правила возврата]. Покупки в магазинах приложений возвращает магазин.',
      ],
    },
    {
      heading: 'Прекращение использования',
      paragraphs: [
        'Вы можете удалить аккаунт в любой момент в настройках. Мы можем приостановить или закрыть аккаунт, нарушающий эти условия. Если мы перестанем предоставлять CareerFit, мы дадим время скачать ваши данные.',
      ],
    },
    {
      heading: 'Ответственность',
      paragraphs: [
        'CareerFit предоставляется «как есть». В пределах, допустимых законом, мы не отвечаем за решения, которые вы или другие принимаете на основе оценки, и за косвенные убытки, а наша общая ответственность ограничена суммой, которую вы заплатили нам за 12 месяцев до претензии. Ничто здесь не ограничивает ваши права по закону о защите прав потребителей.',
      ],
    },
    {
      heading: 'Право и изменения',
      paragraphs: [
        'К этим условиям применяется право [провинция и страна]. Если мы существенно их изменим, мы попросим вашего согласия, прежде чем вы продолжите. Вопросы: [адрес электронной почты поддержки].',
      ],
    },
  ],
};

const scoringEn: LegalDoc = {
  title: 'How the score works',
  updated: 'Last updated 13 November 2026',
  intro:
    'Your score, out of 100, estimates how competitive your resume is for one job in one region. It is plain arithmetic: the same resume and job always give the same score, and every point has a written reason.',
  sections: [
    {
      heading: 'What it adds up',
      paragraphs: [
        'Six parts, weighted for the job’s field. For most jobs: skills the job requires 40 points, other useful skills 10, experience 20, education 15, portfolio 5 and seniority 10. Health jobs weigh education more, senior management weighs experience and seniority more, and so on.',
      ],
      items: [
        'Required and useful skills come from ESCO, the EU’s official list of what each occupation involves. Showing 75% of the required ones earns full marks for that part.',
        'Experience and education are compared with what Canadian job ads for that occupation and region ask for, from Job Bank.',
        'If there isn’t enough market data for a part, it is left out and its points are shared among the others. The report says so.',
      ],
    },
    {
      heading: 'Where AI comes in',
      paragraphs: [
        'AI reads the resume into a list of jobs, studies and skills, and decides which of the job’s skills the resume shows: yes, partly or no. It has to point to evidence in the resume, and code throws out any claim without it. Similar skills it missed get partial credit by meaning, not by AI.',
        'AI does not choose the score. The formula does.',
      ],
    },
    {
      heading: 'What it never uses',
      paragraphs: [
        'The formula has no input for your name, age, gender, nationality, ethnicity, religion, family, health, disability or where you were born, and we remove those details from the resume before AI reads it. We test this on every change with a fake AI that would punish any such detail it saw, and audit the real model by swapping these details and comparing scores.',
      ],
    },
    {
      heading: 'Its limits',
      items: [
        'Canadian job ads on Job Bank list pay, education and experience, but not skills, so skills come from the official description of the occupation, not from what employers ask for this week.',
        'A resume that describes skills in unusual words may get less credit than it should. The report shows what was found and what wasn’t, so you can check.',
        'The score can’t see interviews, references, networks or anything not in the resume.',
      ],
    },
    {
      heading: 'Using it well',
      paragraphs: [
        'Look at the gaps first: they are ranked by how much closing each one would really raise the score. Change your resume only to show what you have actually done, then run it again to see your progress.',
      ],
    },
  ],
};

const scoringRu: LegalDoc = {
  title: 'Как считается оценка',
  updated: 'Обновлено 13 ноября 2026 г.',
  intro:
    'Оценка из 100 показывает, насколько конкурентно ваше резюме для одной вакансии в одном регионе. Это простая арифметика: одно и то же резюме и вакансия всегда дают одну и ту же оценку, и у каждого балла есть письменное объяснение.',
  sections: [
    {
      heading: 'Из чего она складывается',
      paragraphs: [
        'Из шести частей с весами для области профессии. Для большинства профессий: обязательные навыки — 40 баллов, другие полезные навыки — 10, опыт — 20, образование — 15, портфолио — 5, уровень — 10. В медицине больше весит образование, у руководителей — опыт и уровень, и так далее.',
      ],
      items: [
        'Обязательные и полезные навыки берутся из ESCO — официального перечня ЕС, описывающего каждую профессию. Если показано 75% обязательных навыков, эта часть получает полный балл.',
        'Опыт и образование сравниваются с тем, что требуют канадские вакансии этой профессии в этом регионе, по данным Job Bank.',
        'Если для какой-то части мало данных рынка, она не учитывается, а её баллы делятся между остальными. Отчёт об этом сообщает.',
      ],
    },
    {
      heading: 'Где участвует ИИ',
      paragraphs: [
        'ИИ превращает резюме в список мест работы, обучения и навыков и решает, какие навыки профессии в резюме видны: да, частично или нет. Он должен указать подтверждение в резюме, и код отбрасывает любое утверждение без него. Похожие навыки, которые он пропустил, получают частичный балл по смыслу, без ИИ.',
        'Оценку выбирает не ИИ, а формула.',
      ],
    },
    {
      heading: 'Что никогда не учитывается',
      paragraphs: [
        'В формуле нет входных данных для имени, возраста, пола, гражданства, национальности, религии, семьи, здоровья, инвалидности или места рождения, а из резюме мы убираем эти сведения до того, как его прочитает ИИ. Мы проверяем это при каждом изменении с поддельным ИИ, который занижал бы оценку, увидев такие сведения, и проверяем настоящую модель, меняя эти сведения и сравнивая оценки.',
      ],
    },
    {
      heading: 'Ограничения',
      items: [
        'Канадские вакансии на Job Bank указывают зарплату, образование и опыт, но не навыки, поэтому навыки берутся из официального описания профессии, а не из того, что работодатели просят на этой неделе.',
        'Если навыки описаны непривычными словами, резюме может получить меньше баллов, чем заслуживает. Отчёт показывает, что найдено, а что нет, — это можно проверить.',
        'Оценка не видит собеседований, рекомендаций, связей и всего, чего нет в резюме.',
      ],
    },
    {
      heading: 'Как ею пользоваться',
      paragraphs: [
        'Начните с пробелов: они упорядочены по тому, насколько их устранение действительно повысит оценку. Меняйте резюме только так, чтобы показать то, что вы действительно делали, и запустите анализ снова, чтобы увидеть прогресс.',
      ],
    },
  ],
};

export const LEGAL: Record<LegalPageId, Record<Locale, LegalDoc>> = {
  privacy: { en: privacyEn, ru: privacyRu },
  terms: { en: termsEn, ru: termsRu },
  'how-scoring-works': { en: scoringEn, ru: scoringRu },
};
