import 'server-only';
import type { Analysis, Report, ScoreResult } from '@careerfit/shared';
import type { Locale } from '@/i18n/config';

/** A finished analysis with its action plan: everything the example page shows. */
export type ExampleAnalysis = Analysis & { result: ScoreResult & { report: Report } };

// The demo's made-up sample resume (apps/api/data/sample-resume.pdf), checked for "software developer"
// in Ontario on 2026-11-27: one real run per language on the local API with OpenRouter's free model,
// from a throwaway account that was deleted afterwards. Kept as the API returned it, except the
// account's ids. `satisfies` checks both against the shared types, so if the result's shape changes,
// the build fails here rather than the page breaking.

const en = {
  id: 'example',
  status: 'completed',
  stage: null,
  documentId: null,
  role: 'software developer',
  region: 'Ontario',
  score: 70,
  result: {
    score: 70,
    categories: [
      {
        key: 'required_skills',
        label: 'Required skills',
        maxPoints: 40,
        points: 30,
        reason:
          'Your resume shows 6 and partly shows 5 of the 15 required skills we checked. Covering 75% earns full marks.',
      },
      {
        key: 'preferred_skills',
        label: 'Other useful skills',
        maxPoints: 10,
        points: 5,
        reason:
          'Your resume shows 2 and partly shows 1 of the 10 other useful skills we checked. Covering 50% earns full marks.',
      },
      {
        key: 'experience',
        label: 'Relevant experience',
        maxPoints: 20,
        points: 20,
        reason:
          'You have 6.9 years of relevant experience, counting: Software Developer, Junior Developer. Typical ads ask for about 2 years.',
      },
      {
        key: 'education',
        label: 'Education',
        maxPoints: 10,
        points: 10,
        reason: "Typical ads ask for a bachelor's degree, and you have a bachelor's degree.",
      },
      {
        key: 'portfolio',
        label: 'Portfolio',
        maxPoints: 15,
        points: 0,
        reason:
          'Projects on your resume that back up skills for this role: 0. Portfolio links you added: 0. 3 of these together earn full marks.',
      },
      {
        key: 'seniority',
        label: 'Seniority',
        maxPoints: 5,
        points: 5,
        reason: 'Your resume reads as mid, and typical ads suit mid level.',
      },
    ],
    notScored: [],
    requiredSkills: [
      {
        name: 'use software libraries',
        level: 'yes',
        evidence: [
          'Skill: Python',
          'Skill: FastAPI',
          'Skill: Django',
          'Skill: pytest',
          'Skill: React',
        ],
      },
      {
        name: 'utilise computer-aided software engineering tools',
        level: 'yes',
        evidence: [
          'Skill: Docker',
          'Skill: Git',
          'Skill: GitHub Actions',
          'Skill: pytest',
          'Skill: Release automation',
          'Skill: CI/CD',
        ],
      },
      {
        name: 'develop software prototype',
        level: 'partly',
        evidence: [
          'Skill: Back-end development',
          'Skill: Internal tools development',
          'Skill: Front-end development',
          'Skill: Dashboard development',
          'Job title: Software Developer',
          'Job title: Junior Developer',
        ],
      },
      {
        name: 'integrated development environment software',
        level: 'partly',
        evidence: ['Job title: Software Developer', 'Job title: Junior Developer'],
      },
      {
        name: 'analyse software specifications',
        level: 'partly',
        evidence: [
          'Skill: Back-end development',
          'Skill: Front-end development',
          'Skill: Database design',
          'Job title: Software Developer',
          'Job title: Junior Developer',
        ],
      },
      {
        name: 'tools for software configuration management',
        level: 'yes',
        evidence: ['Skill: Git', 'Skill: GitHub Actions'],
      },
      {
        name: 'debug software',
        level: 'yes',
        evidence: [
          'Skill: pytest',
          'Skill: Automated testing',
          'Job title: Software Developer',
          'Job title: Junior Developer',
        ],
      },
      {
        name: 'use technical drawing software',
        level: 'no',
        evidence: [],
      },
      {
        name: 'computer programming',
        level: 'yes',
        evidence: [
          'Skill: Python',
          'Skill: TypeScript',
          'Job title: Software Developer',
          'Job title: Junior Developer',
          'Degree: Bachelor of Science Computer Science',
        ],
      },
      {
        name: 'project management',
        level: 'no',
        evidence: [],
      },
      {
        name: 'use software design patterns',
        level: 'partly',
        evidence: [
          'Skill: Back-end development',
          'Skill: Front-end development',
          'Skill: Database design',
          'Job title: Software Developer',
          'Job title: Junior Developer',
        ],
      },
      {
        name: 'manage engineering project',
        level: 'no',
        evidence: [],
      },
      {
        name: 'provide technical documentation',
        level: 'no',
        evidence: [],
      },
      {
        name: 'ICT debugging tools',
        level: 'partly',
        evidence: ['Skill: pytest', 'Skill: Automated testing', 'Job title: Software Developer'],
      },
      {
        name: 'engineering processes',
        level: 'yes',
        evidence: [
          'Skill: GitHub Actions',
          'Skill: Service packaging',
          'Skill: Automated testing',
          'Skill: Release automation',
          'Skill: CI/CD',
          'Skill: Code review',
        ],
      },
    ],
    preferredSkills: [
      {
        name: 'Visual Studio .NET',
        level: 'no',
        evidence: [],
      },
      {
        name: 'software anomalies',
        level: 'yes',
        evidence: ['Skill: pytest', 'Skill: Automated testing', 'Skill: Code review'],
      },
      {
        name: 'Salt (tools for software configuration management)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Jenkins (tools for software configuration management)',
        level: 'partly',
        evidence: ['Skill: GitHub Actions', 'Skill: CI/CD'],
      },
      {
        name: 'Microsoft Visual C++',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Prolog (computer programming)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Eclipse (integrated development environment software)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'OpenEdge Advanced Business Language',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Puppet (tools for software configuration management)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'design user interface',
        level: 'yes',
        evidence: ['Skill: React', 'Skill: Front-end development', 'Skill: Dashboard development'],
      },
    ],
    salary: {
      low: 119000,
      high: 130350,
      marketMedian: 120000,
      currency: 'CAD',
      sampleSize: 143,
      region: 'Ontario',
      concentrated: false,
      basis:
        'Placed within the middle half of 143 job ads in Ontario, based on your experience and skills.',
    },
    confidence: {
      level: 'high',
      reasons: ['Plenty of job ads and a full skill list for this occupation.'],
    },
    occupationCode: '21232',
    occupationName: 'Software developers and programmers',
    region: 'Ontario',
    weightsUsed: 'Natural and applied sciences',
    asOf: '2026-11-27',
    marketLatestPosting: '2026-10-31',
    disclaimer:
      'This is an estimate to help you plan, not a guarantee of being hired or of any salary. It was made with AI, which can make mistakes.',
    report: {
      gaps: [
        {
          kind: 'portfolio',
          title: 'Portfolio work that shows these skills',
          pointsAvailable: 15,
          detail:
            'Projects on your resume that back up skills for this role: 0. Portfolio links you added: 0. 3 of these together earn full marks.',
        },
        {
          kind: 'required_skill',
          title: 'use technical drawing software',
          pointsAvailable: 4,
          detail: 'Not found on your resume. Essential in the official list for this occupation.',
        },
        {
          kind: 'required_skill',
          title: 'project management',
          pointsAvailable: 4,
          detail: 'Not found on your resume. Essential in the official list for this occupation.',
        },
        {
          kind: 'required_skill',
          title: 'manage engineering project',
          pointsAvailable: 4,
          detail: 'Not found on your resume. Essential in the official list for this occupation.',
        },
        {
          kind: 'required_skill',
          title: 'provide technical documentation',
          pointsAvailable: 4,
          detail: 'Not found on your resume. Essential in the official list for this occupation.',
        },
        {
          kind: 'required_skill',
          title: 'develop software prototype',
          pointsAvailable: 2,
          detail:
            'Only partly shown on your resume. Essential in the official list for this occupation.',
        },
        {
          kind: 'required_skill',
          title: 'integrated development environment software',
          pointsAvailable: 2,
          detail:
            'Only partly shown on your resume. Essential in the official list for this occupation.',
        },
        {
          kind: 'required_skill',
          title: 'analyse software specifications',
          pointsAvailable: 2,
          detail:
            'Only partly shown on your resume. Essential in the official list for this occupation.',
        },
      ],
      actions: [
        {
          gap: 'Portfolio work that shows these skills',
          kind: 'project',
          title: 'Add a project that shows your skills',
          details:
            'Complete a small piece of work for this occupation and describe it on your resume.',
          expectedResult: 'A finished example you can show employers.',
          providers: [],
          effortWeeks: 4,
          priority: 'high',
          uncertain: false,
        },
        {
          gap: 'use technical drawing software',
          kind: 'course',
          title: 'Technical drawing and diagramming for software systems',
          details:
            'Learn to use technical drawing software to create architecture, data-flow, database, and interface diagrams for software projects.',
          expectedResult: 'A set of clear diagrams for a sample software system.',
          providers: ['LinkedIn Learning', 'Udemy', 'a local college'],
          effortWeeks: 3,
          priority: 'medium',
          uncertain: true,
        },
        {
          gap: 'project management',
          kind: 'course',
          title: 'Project management fundamentals for software delivery',
          details:
            'Learn scope, scheduling, risk, stakeholder communication, and delivery basics relevant to software teams.',
          expectedResult:
            'A simple project plan template and notes on applying it to a software project.',
          providers: ['Coursera', 'edX', 'LinkedIn Learning', 'a professional association'],
          effortWeeks: 4,
          priority: 'medium',
          uncertain: false,
        },
        {
          gap: 'manage engineering project',
          kind: 'experience',
          title: 'Lead a small engineering project',
          details:
            'Volunteer or take a lead role on a small internal, community, or open-source software project, coordinating tasks, timeline, risks, and updates.',
          expectedResult:
            'A delivered project increment with a plan, status updates, and retrospective notes.',
          providers: ['a professional association', 'a government employment service'],
          effortWeeks: 12,
          priority: 'medium',
          uncertain: true,
        },
        {
          gap: 'provide technical documentation',
          kind: 'project',
          title: 'Technical documentation package for a software service',
          details:
            'Create documentation for a small service covering architecture, setup, API usage, testing, release steps, and troubleshooting.',
          expectedResult: 'A README or docs folder that another developer can follow.',
          providers: [],
          effortWeeks: 3,
          priority: 'medium',
          uncertain: false,
        },
      ],
      rewrites: [
        {
          before:
            '- Built and maintained the back end of the customer delivery-tracking portal, used by 20,000 people a day.',
          after:
            'Built and maintained the back end of the customer delivery-tracking portal, which is used by 20,000 people a day.',
        },
        {
          before:
            '- Designed the database for shipment records and wrote the month-end reports, cutting reporting from 3 days to 1.',
          after:
            'Designed the database for shipment records and wrote the month-end reports, reducing reporting from 3 days to 1.',
        },
        {
          before:
            '- Packaged the services so they run the same on every machine, and automated testing and releases on every change.',
          after:
            'Packaged the services to run the same on every machine and automated testing and releases on every change.',
        },
      ],
      alternativeRoles: [
        {
          occupationCode: '21231',
          occupationName: 'Software engineers and designers',
          score: 80,
          fit: 'strong',
          reason:
            'You show 11 and partly show 4 of the 15 required skills, including ICT debugging tools. Your experience meets what typical ads ask for.',
          salary: {
            low: 131099,
            high: 143874,
            marketMedian: 121680,
            currency: 'CAD',
            sampleSize: 69,
            region: 'Ontario',
            concentrated: false,
            basis:
              'Placed within the middle half of 69 job ads in Ontario, based on your experience and skills.',
          },
          payComparedToTarget: 'higher',
          mayNeedLicence: false,
        },
        {
          occupationCode: '21234',
          occupationName: 'Web developers and programmers',
          score: 76,
          fit: 'strong',
          reason:
            'You show 7 and partly show 6 of the 15 required skills, including web programming. Your experience meets what typical ads ask for. The main thing to add: content development processes.',
          salary: {
            low: 101221,
            high: 115800,
            marketMedian: 83720,
            currency: 'CAD',
            sampleSize: 36,
            region: 'Ontario',
            concentrated: false,
            basis:
              'Placed within the middle half of 36 job ads in Ontario, based on your experience and skills.',
          },
          payComparedToTarget: 'lower',
          mayNeedLicence: false,
        },
        {
          occupationCode: '21230',
          occupationName: 'Computer systems developers and programmers',
          score: 69,
          fit: 'strong',
          reason:
            'You show 6 and partly show 5 of the 15 required skills, including use software libraries. Your experience meets what typical ads ask for. The main thing to add: use technical drawing software.',
          salary: {
            low: 76699,
            high: 84315,
            marketMedian: 75728,
            currency: 'CAD',
            sampleSize: 35,
            region: 'Canada',
            concentrated: false,
            basis:
              'Placed within the middle half of 35 job ads in Canada, based on your experience and skills.',
          },
          payComparedToTarget: 'lower',
          mayNeedLicence: false,
        },
      ],
      plan: {
        thirtyDays: [
          "Update your resume using the suggested rewrites, where they're true for you",
          'Add a project that shows your skills (about 4 weeks)',
        ],
        sixtyDays: [
          'Technical drawing and diagramming for software systems (about 3 weeks)',
          'Technical documentation package for a software service (about 3 weeks)',
        ],
        ninetyDays: [
          'Project management fundamentals for software delivery (about 4 weeks)',
          'Run a new analysis with your updated resume to see your progress',
        ],
        later: ['Lead a small engineering project (about 12 weeks)'],
      },
      notes: [
        "Gaps are ranked by their effect on your score, using the official skill list for this occupation. The job ads we use don't list skills, so we can't say how often employers ask for each one.",
        'A skill marked as not found may just be missing from your resume. If you have it, add it with a real example.',
        'Effort is a rough estimate, and suggestions were written by AI. Check that a course or certification is current and suits you before paying for it.',
      ],
    },
    reportError: null,
  },
  errorCode: null,
  createdAt: '2026-11-27T22:49:42.490332+00:00',
  completedAt: '2026-11-27T22:49:43.602457+00:00',
} satisfies ExampleAnalysis;

const ru = {
  id: 'example',
  status: 'completed',
  stage: null,
  documentId: null,
  role: 'software developer',
  region: 'Ontario',
  score: 70,
  result: {
    score: 70,
    categories: [
      {
        key: 'required_skills',
        label: 'Обязательные навыки',
        maxPoints: 40,
        points: 30,
        reason:
          'Проверено обязательных навыков: 15. В резюме показано: 6, частично: 5. Максимальный балл даётся при охвате 75%.',
      },
      {
        key: 'preferred_skills',
        label: 'Другие полезные навыки',
        maxPoints: 10,
        points: 5,
        reason:
          'Проверено других полезных навыков: 10. В резюме показано: 2, частично: 1. Максимальный балл даётся при охвате 50%.',
      },
      {
        key: 'experience',
        label: 'Подходящий опыт',
        maxPoints: 20,
        points: 20,
        reason:
          'Ваш подходящий опыт: 6,9 года. Учтено: Software Developer, Junior Developer. Обычно в объявлениях просят примерно 2 года.',
      },
      {
        key: 'education',
        label: 'Образование',
        maxPoints: 10,
        points: 10,
        reason: 'Обычно просят: степень бакалавра. У вас: степень бакалавра.',
      },
      {
        key: 'portfolio',
        label: 'Портфолио',
        maxPoints: 15,
        points: 0,
        reason:
          'Проектов в резюме, подтверждающих навыки для этой работы: 0. Добавлено ссылок на портфолио: 0. Всего для максимального балла нужно: 3.',
      },
      {
        key: 'seniority',
        label: 'Уровень',
        maxPoints: 5,
        points: 5,
        reason:
          'Ваш уровень по резюме: специалист среднего уровня. Обычно объявлениям подходит: специалист среднего уровня.',
      },
    ],
    notScored: [],
    requiredSkills: [
      {
        name: 'использование библиотек программного обеспечения',
        level: 'yes',
        evidence: [
          'Навык: Python',
          'Навык: FastAPI',
          'Навык: Django',
          'Навык: pytest',
          'Навык: React',
        ],
      },
      {
        name: 'использование инструментов компьютерно-ассистированного проектирования ПО',
        level: 'yes',
        evidence: [
          'Навык: Docker',
          'Навык: Git',
          'Навык: GitHub Actions',
          'Навык: pytest',
          'Навык: Release automation',
          'Навык: CI/CD',
        ],
      },
      {
        name: 'разработка прототипа программного обеспечения',
        level: 'partly',
        evidence: [
          'Навык: Back-end development',
          'Навык: Internal tools development',
          'Навык: Front-end development',
          'Навык: Dashboard development',
          'Должность: Software Developer',
          'Должность: Junior Developer',
        ],
      },
      {
        name: 'среды разработки интегрированного типа (IDE)',
        level: 'partly',
        evidence: ['Должность: Software Developer', 'Должность: Junior Developer'],
      },
      {
        name: 'анализ спецификаций программного обеспечения',
        level: 'partly',
        evidence: [
          'Навык: Back-end development',
          'Навык: Front-end development',
          'Навык: Database design',
          'Должность: Software Developer',
          'Должность: Junior Developer',
        ],
      },
      {
        name: 'инструменты управления конфигурацией ПО',
        level: 'yes',
        evidence: ['Навык: Git', 'Навык: GitHub Actions'],
      },
      {
        name: 'отладка программного обеспечения',
        level: 'yes',
        evidence: [
          'Навык: pytest',
          'Навык: Automated testing',
          'Должность: Software Developer',
          'Должность: Junior Developer',
        ],
      },
      {
        name: 'использование программного обеспечения для технической графики',
        level: 'no',
        evidence: [],
      },
      {
        name: 'программирование на компьютере',
        level: 'yes',
        evidence: [
          'Навык: Python',
          'Навык: TypeScript',
          'Должность: Software Developer',
          'Должность: Junior Developer',
          'Образование: Bachelor of Science Computer Science',
        ],
      },
      {
        name: 'управление проектами',
        level: 'no',
        evidence: [],
      },
      {
        name: 'использование паттернов проектирования ПО',
        level: 'partly',
        evidence: [
          'Навык: Back-end development',
          'Навык: Front-end development',
          'Навык: Database design',
          'Должность: Software Developer',
          'Должность: Junior Developer',
        ],
      },
      {
        name: 'управление инженерным проектом',
        level: 'no',
        evidence: [],
      },
      {
        name: 'предоставление технической документации',
        level: 'no',
        evidence: [],
      },
      {
        name: 'инструменты отладки ИКТ',
        level: 'partly',
        evidence: ['Навык: pytest', 'Навык: Automated testing', 'Должность: Software Developer'],
      },
      {
        name: 'инженерные процессы',
        level: 'yes',
        evidence: [
          'Навык: GitHub Actions',
          'Навык: Service packaging',
          'Навык: Automated testing',
          'Навык: Release automation',
          'Навык: CI/CD',
          'Навык: Code review',
        ],
      },
    ],
    preferredSkills: [
      {
        name: 'Visual Studio .NET',
        level: 'no',
        evidence: [],
      },
      {
        name: 'аномалии ПО',
        level: 'yes',
        evidence: ['Навык: pytest', 'Навык: Automated testing', 'Навык: Code review'],
      },
      {
        name: 'Salt (инструменты управления конфигурацией ПО)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Jenkins (инструменты управления конфигурацией ПО)',
        level: 'partly',
        evidence: ['Навык: GitHub Actions', 'Навык: CI/CD'],
      },
      {
        name: 'Microsoft Visual C++',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Prolog (программирование на компьютере)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Eclipse (среда разработки интегрированного типа)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'OpenEdge Advanced Business Language',
        level: 'no',
        evidence: [],
      },
      {
        name: 'Puppet (инструменты управления конфигурацией ПО)',
        level: 'no',
        evidence: [],
      },
      {
        name: 'проектирование пользовательского интерфейса',
        level: 'yes',
        evidence: ['Навык: React', 'Навык: Front-end development', 'Навык: Dashboard development'],
      },
    ],
    salary: {
      low: 119000,
      high: 130350,
      marketMedian: 120000,
      currency: 'CAD',
      sampleSize: 143,
      region: 'Ontario',
      concentrated: false,
      basis:
        'Диапазон выбран внутри средней половины зарплат из объявлений (143, регион: Онтарио) с учётом вашего опыта и навыков.',
    },
    confidence: {
      level: 'high',
      reasons: ['Много объявлений и полный перечень навыков для этой профессии.'],
    },
    occupationCode: '21232',
    occupationName: 'Разработчики программного обеспечения и программисты',
    region: 'Ontario',
    weightsUsed: 'Естественные и прикладные науки',
    asOf: '2026-11-27',
    marketLatestPosting: '2026-10-31',
    disclaimer:
      'Это оценка, которая помогает планировать, а не гарантия трудоустройства или какой-либо зарплаты. Она сделана с помощью ИИ, который может ошибаться.',
    report: {
      gaps: [
        {
          kind: 'portfolio',
          title: 'Работы в портфолио, показывающие эти навыки',
          pointsAvailable: 15,
          detail:
            'Проектов в резюме, подтверждающих навыки для этой работы: 0. Добавлено ссылок на портфолио: 0. Всего для максимального балла нужно: 3.',
        },
        {
          kind: 'required_skill',
          title: 'использование программного обеспечения для технической графики',
          pointsAvailable: 4,
          detail:
            'В резюме не найден. В официальном перечне для этой профессии указан как обязательный.',
        },
        {
          kind: 'required_skill',
          title: 'управление проектами',
          pointsAvailable: 4,
          detail:
            'В резюме не найден. В официальном перечне для этой профессии указан как обязательный.',
        },
        {
          kind: 'required_skill',
          title: 'управление инженерным проектом',
          pointsAvailable: 4,
          detail:
            'В резюме не найден. В официальном перечне для этой профессии указан как обязательный.',
        },
        {
          kind: 'required_skill',
          title: 'предоставление технической документации',
          pointsAvailable: 4,
          detail:
            'В резюме не найден. В официальном перечне для этой профессии указан как обязательный.',
        },
        {
          kind: 'required_skill',
          title: 'разработка прототипа программного обеспечения',
          pointsAvailable: 2,
          detail:
            'В резюме показан лишь частично. В официальном перечне для этой профессии указан как обязательный.',
        },
        {
          kind: 'required_skill',
          title: 'среды разработки интегрированного типа (IDE)',
          pointsAvailable: 2,
          detail:
            'В резюме показан лишь частично. В официальном перечне для этой профессии указан как обязательный.',
        },
        {
          kind: 'required_skill',
          title: 'анализ спецификаций программного обеспечения',
          pointsAvailable: 2,
          detail:
            'В резюме показан лишь частично. В официальном перечне для этой профессии указан как обязательный.',
        },
      ],
      actions: [
        {
          gap: 'Работы в портфолио, показывающие эти навыки',
          kind: 'project',
          title: 'Добавьте проект, показывающий ваши навыки',
          details: 'Выполните небольшую работу по этой профессии и опишите её в резюме.',
          expectedResult: 'Готовый пример, который можно показать работодателям.',
          providers: [],
          effortWeeks: 4,
          priority: 'high',
          uncertain: false,
        },
        {
          gap: 'использование программного обеспечения для технической графики',
          kind: 'course',
          title: 'Техническое черчение и схемы для ПО',
          details:
            'Изучите основы технических диаграмм, схем архитектуры, потоков данных и интерфейсов в подходящем программном обеспечении для черчения.',
          expectedResult:
            'Умение создавать понятные технические схемы и чертежи для документации проекта.',
          providers: [
            'LinkedIn Learning',
            'Udemy',
            'a local college',
            'a university continuing education program',
          ],
          effortWeeks: 3,
          priority: 'medium',
          uncertain: true,
        },
        {
          gap: 'управление проектами',
          kind: 'course',
          title: 'Основы управления проектами в разработке',
          details:
            'Пройдите курс по планированию, приоритизации, срокам, рискам и коммуникации в небольших инженерных командах.',
          expectedResult: 'Базовые инструменты и шаблоны для планирования задач и контроля сроков.',
          providers: [
            'Coursera',
            'edX',
            'LinkedIn Learning',
            'Udemy',
            'a professional association',
          ],
          effortWeeks: 4,
          priority: 'medium',
          uncertain: false,
        },
        {
          gap: 'управление инженерным проектом',
          kind: 'experience',
          title: 'Опыт ведения небольшого инженерного проекта',
          details:
            'Возьмите роль координатора или волонтёра в небольшом проекте: внутренний инструмент, некоммерческий сайт или студенческий хакатон; ведите задачи, сроки и отчётность.',
          expectedResult:
            'Практический опыт управления инженерным проектом и подтверждённый результат в виде описания проекта.',
          providers: ['a professional association', 'a government employment service'],
          effortWeeks: 12,
          priority: 'medium',
          uncertain: true,
        },
        {
          gap: 'предоставление технической документации',
          kind: 'project',
          title: 'Пакет технической документации',
          details:
            'Подготовьте документацию к существующему проекту: обзор архитектуры, инструкция по запуску, описание API, схемы и руководство по устранению ошибок.',
          expectedResult:
            'Комплект технической документации, который можно приложить к портфолио или использовать в команде.',
          providers: [],
          effortWeeks: 3,
          priority: 'medium',
          uncertain: false,
        },
      ],
      rewrites: [
        {
          before:
            '- Built and maintained the back end of the customer delivery-tracking portal, used by 20,000 people a day.',
          after:
            'Built and maintained the back end of the customer delivery-tracking portal, which 20,000 people use each day.',
        },
        {
          before:
            '- Designed the database for shipment records and wrote the month-end reports, cutting reporting from 3 days to 1.',
          after:
            'Designed the database for shipment records and wrote month-end reports, cutting reporting from 3 days to 1.',
        },
        {
          before:
            '- Packaged the services so they run the same on every machine, and automated testing and releases on every change.',
          after:
            'Packaged the services to run the same on every machine and automated testing and releases for every change.',
        },
      ],
      alternativeRoles: [
        {
          occupationCode: '21231',
          occupationName: 'Инженеры-программисты и дизайнеры ПО',
          score: 80,
          fit: 'strong',
          reason:
            'Обязательных навыков всего: 15. Вы показываете: 11, частично: 4. Например: инструменты отладки ИКТ. Ваш опыт соответствует тому, что обычно просят в объявлениях.',
          salary: {
            low: 131099,
            high: 143874,
            marketMedian: 121680,
            currency: 'CAD',
            sampleSize: 69,
            region: 'Ontario',
            concentrated: false,
            basis:
              'Диапазон выбран внутри средней половины зарплат из объявлений (69, регион: Онтарио) с учётом вашего опыта и навыков.',
          },
          payComparedToTarget: 'higher',
          mayNeedLicence: false,
        },
        {
          occupationCode: '21234',
          occupationName: 'Веб-разработчики и программисты',
          score: 76,
          fit: 'strong',
          reason:
            'Обязательных навыков всего: 15. Вы показываете: 7, частично: 6. Например: веб-программирование. Ваш опыт соответствует тому, что обычно просят в объявлениях. Что добавить в первую очередь: процессы разработки контента.',
          salary: {
            low: 101221,
            high: 115800,
            marketMedian: 83720,
            currency: 'CAD',
            sampleSize: 36,
            region: 'Ontario',
            concentrated: false,
            basis:
              'Диапазон выбран внутри средней половины зарплат из объявлений (36, регион: Онтарио) с учётом вашего опыта и навыков.',
          },
          payComparedToTarget: 'lower',
          mayNeedLicence: false,
        },
        {
          occupationCode: '21230',
          occupationName: 'Разработчики компьютерных систем и программисты',
          score: 69,
          fit: 'strong',
          reason:
            'Обязательных навыков всего: 15. Вы показываете: 6, частично: 5. Например: использование библиотек программного обеспечения. Ваш опыт соответствует тому, что обычно просят в объявлениях. Что добавить в первую очередь: использование программного обеспечения для технической графики.',
          salary: {
            low: 76699,
            high: 84315,
            marketMedian: 75728,
            currency: 'CAD',
            sampleSize: 35,
            region: 'Canada',
            concentrated: false,
            basis:
              'Диапазон выбран внутри средней половины зарплат из объявлений (35, регион: вся Канада) с учётом вашего опыта и навыков.',
          },
          payComparedToTarget: 'lower',
          mayNeedLicence: false,
        },
      ],
      plan: {
        thirtyDays: [
          'Обновите резюме, используя предложенные формулировки там, где они верны для вас',
          'Добавьте проект, показывающий ваши навыки (примерно 4 недели)',
        ],
        sixtyDays: [
          'Техническое черчение и схемы для ПО (примерно 3 недели)',
          'Пакет технической документации (примерно 3 недели)',
        ],
        ninetyDays: [
          'Основы управления проектами в разработке (примерно 4 недели)',
          'Запустите новый анализ с обновлённым резюме, чтобы увидеть прогресс',
        ],
        later: ['Опыт ведения небольшого инженерного проекта (примерно 12 недель)'],
      },
      notes: [
        'Пробелы упорядочены по влиянию на вашу оценку на основе официального перечня навыков для этой профессии. В используемых объявлениях навыки не указаны, поэтому мы не можем сказать, как часто работодатели просят каждый из них.',
        'Навык с пометкой «не найден» может просто отсутствовать в резюме. Если он у вас есть, добавьте его с реальным примером.',
        'Срок указан примерно, а рекомендации написаны ИИ. Перед оплатой проверьте, что курс или сертификат актуален и подходит вам.',
      ],
    },
    reportError: null,
  },
  errorCode: null,
  createdAt: '2026-11-27T22:52:22.524723+00:00',
  completedAt: '2026-11-27T22:52:23.620467+00:00',
} satisfies ExampleAnalysis;

export const EXAMPLE_ANALYSES: Record<Locale, ExampleAnalysis> = { en, ru };
