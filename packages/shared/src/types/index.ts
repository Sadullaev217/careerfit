// Core domain types shared between web, mobile, and API

export type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert';

export type DocumentType = 'resume' | 'cover_letter' | 'portfolio_link';

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type SubscriptionPlan = 'free' | 'pro';

export interface Me {
  id: string;
  email: string | null;
}

/** The agreement accepted before CareerFit reads a resume. */
export interface ConsentStatus {
  /** The version to show and send back when accepting. */
  version: string;
  accepted: boolean;
  acceptedAt: string | null;
  /** Where resumes are read: CareerFit's own server, or a hosted model through OpenRouter. */
  aiProcessing: 'self_hosted' | 'openrouter';
}

export interface PlanInfo {
  plan: SubscriptionPlan;
  /** Stripe's status. "past_due" means a payment failed and Stripe is retrying; Pro continues meanwhile. */
  status: string;
  provider: 'stripe' | 'revenuecat' | null;
  cancelAtPeriodEnd: boolean;
  currentPeriodEnd: string | null;
  analysesUsed: number;
  /** null means unlimited (Pro). */
  analysesLimit: number | null;
  /** The day the monthly limit starts again, as YYYY-MM-DD (midnight UTC). */
  limitResetsAt: string;
  /** Analyses whose detailed PDF report has been bought. */
  purchasedReports: string[];
  /** The public demo: everything is unlocked and nothing can be bought, so payments are hidden. */
  demo: boolean;
}

export interface CheckoutLink {
  url: string;
}

export interface TailoredRewrite {
  before: string;
  after: string;
  /** The job skill this line now shows. */
  skill: string;
}

export interface TailoredRewrites {
  job: string;
  /** null until the resume has been tailored for this result. */
  rewrites: TailoredRewrite[] | null;
}

export interface ProgressPoint {
  analysisId: string;
  date: string;
  score: number;
}

export interface ProgressTrack {
  role: string;
  region: string | null;
  points: ProgressPoint[];
  /** Latest score minus the first, or null with only one run. */
  change: number | null;
}

export interface RoleSuggestion {
  title: string;
  occupationCode: string;
  occupationName: string;
}

export interface Profile {
  id: string;
  displayName: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Document {
  id: string;
  type: DocumentType;
  fileName: string | null;
  url: string | null;
  status: 'pending' | 'parsing' | 'ready' | 'failed';
  errorCode: string | null;
  errorMessage: string | null;
  extractionStatus: 'pending' | 'running' | 'ready' | 'failed' | null;
  extractionErrorCode: string | null;
  extractionErrorMessage: string | null;
  createdAt: string;
  /** Uploaded files are deleted 90 days after upload unless kept. */
  keep: boolean;
  /** When the file will be deleted, or null if it won't be (kept, already deleted, or a link). */
  deleteAfter: string | null;
  fileDeletedAt: string | null;
}

export interface ExtractedProfile {
  skills: Array<{
    name: string;
    name_en: string;
    level: string;
    years: number | null;
    confidence: number;
  }>;
  work_history: Array<{
    title_en: string;
    employer: string | null;
    start_date: string | null;
    end_date: string | null;
    is_current: boolean;
  }>;
  education: Array<{
    degree: string | null;
    field_of_study: string | null;
    institution: string | null;
    end_year: number | null;
  }>;
  certifications: Array<{ name: string; issuer: string | null; year: number | null }>;
  languages: Array<{ name_en: string; level: string | null }>;
  projects: Array<{ name: string; demonstrates_en: string[] }>;
  industry_en: string | null;
  seniority: string;
  flags: Array<{ field: string; issue: 'missing' | 'ambiguous' }>;
}

export interface DocumentAnalysis {
  profile: ExtractedProfile;
  matchedSkills: Array<{
    sourceName: string | null;
    canonicalName: string;
    escoId: string | null;
    matchScore: number | null;
  }>;
  promptVersion: string;
  model: string;
  truncated: boolean;
  createdAt: string;
}

export interface MarketRequirements {
  role: string;
  matchedTitle: string;
  occupationCode: string;
  occupationName: string;
  region: string;
  sampleSize: number;
  salary: {
    p25: number;
    median: number;
    p75: number;
    currency: string;
    period: 'yearly';
    sampleSize: number;
    region: string;
    confidence: 'low' | 'medium' | 'high';
    concentrated: boolean;
  } | null;
  requiredSkills: string[];
  preferredSkills: string[];
  education: Record<string, number>;
  experience: Record<string, number>;
  latestPosting: string | null;
  sources: string[];
  limitations: string;
}

export interface Skill {
  id: string;
  name: string;
  escoId: string | null;
  category: string | null;
}

export interface ProfileSkill {
  skillId: string;
  skill: Skill;
  level: SkillLevel;
  yearsOfExperience: number;
}

export interface TargetRole {
  id: string;
  userId: string;
  title: string;
  region: string;
  industry: string | null;
}

export interface JudgedSkill {
  name: string;
  level: 'yes' | 'partly' | 'no';
  evidence: string[];
}

export interface ScoreCategory {
  key: string;
  label: string;
  maxPoints: number;
  points: number;
  reason: string;
}

export interface ScoreResult {
  score: number;
  categories: ScoreCategory[];
  notScored: string[];
  requiredSkills: JudgedSkill[];
  preferredSkills: JudgedSkill[];
  salary: {
    low: number;
    high: number;
    marketMedian: number;
    currency: string;
    sampleSize: number;
    region: string;
    concentrated: boolean;
    basis: string;
  } | null;
  confidence: { level: 'low' | 'medium' | 'high'; reasons: string[] };
  occupationCode: string;
  occupationName: string;
  region: string;
  weightsUsed: string;
  asOf: string;
  marketLatestPosting: string | null;
  disclaimer: string;
  report?: Report | null;
  reportError?: string | null;
}

export interface Gap {
  kind: 'required_skill' | 'preferred_skill' | 'experience' | 'education' | 'portfolio';
  title: string;
  pointsAvailable: number;
  detail: string;
}

export interface RecommendedAction {
  gap: string;
  kind: 'course' | 'certification' | 'project' | 'experience';
  title: string;
  details: string;
  expectedResult: string | null;
  providers: string[];
  effortWeeks: number;
  priority: 'high' | 'medium' | 'low';
  uncertain: boolean;
}

export interface ResumeRewrite {
  before: string;
  after: string;
}

export interface AlternativeRole {
  occupationCode: string;
  occupationName: string;
  score: number;
  fit: 'strong' | 'one_step' | 'bigger_step';
  reason: string;
  salary: ScoreResult['salary'];
  payComparedToTarget: 'higher' | 'similar' | 'lower' | null;
  mayNeedLicence: boolean;
}

export interface ImprovementPlan {
  thirtyDays: string[];
  sixtyDays: string[];
  ninetyDays: string[];
  later: string[];
}

export interface Report {
  gaps: Gap[];
  actions: RecommendedAction[];
  rewrites: ResumeRewrite[];
  alternativeRoles: AlternativeRole[];
  plan: ImprovementPlan;
  notes: string[];
}

export interface Analysis {
  id: string;
  status: AnalysisStatus;
  stage: 'matching' | 'planning' | 'alternatives' | null;
  documentId: string | null;
  role: string | null;
  region: string | null;
  score: number | null;
  result: ScoreResult | null;
  errorCode: string | null;
  createdAt: string;
  completedAt: string | null;
}

export interface HealthResponse {
  status: 'ok';
  version: string;
  timestamp: string;
}
