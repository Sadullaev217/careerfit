// Core domain types shared between web, mobile, and API

export type SkillLevel = 'beginner' | 'intermediate' | 'advanced' | 'expert';

export type DocumentType = 'resume' | 'cover_letter' | 'portfolio_link';

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type SubscriptionPlan = 'free' | 'pro';

export interface Me {
  id: string;
  email: string | null;
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
  extractionErrorMessage: string | null;
  createdAt: string;
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

export interface ScoreBreakdown {
  requiredSkills: { score: number; reason: string };
  preferredSkills: { score: number; reason: string };
  experience: { score: number; reason: string };
  education: { score: number; reason: string };
  portfolio: { score: number; reason: string };
  seniority: { score: number; reason: string };
}

export interface SalaryRange {
  min: number;
  max: number;
  median: number;
  currency: string;
  period: 'yearly' | 'monthly';
}

export interface RecommendedAction {
  type: 'course' | 'project' | 'resume_rewrite';
  skill: string;
  description: string;
  effortWeeks: number;
  priority: 'high' | 'medium' | 'low';
  beforeExample?: string;
  afterExample?: string;
}

export interface AlternativeRole {
  title: string;
  matchScore: number;
  reason: string;
  salaryRange: SalaryRange;
}

export interface ImprovementPlan {
  thirtyDays: string[];
  sixtyDays: string[];
  ninetyDays: string[];
}

export interface AnalysisResult {
  overallScore: number;
  confidence: number;
  scoreBreakdown: ScoreBreakdown;
  salaryRange: SalaryRange;
  missingSkills: Array<{ skill: string; impact: number; requiredByPercent: number }>;
  recommendedActions: RecommendedAction[];
  alternativeRoles: AlternativeRole[];
  improvementPlan: ImprovementPlan;
  disclaimer: string;
}

export interface Analysis {
  id: string;
  userId: string;
  targetRoleId: string;
  status: AnalysisStatus;
  result: AnalysisResult | null;
  createdAt: string;
  completedAt: string | null;
}

export interface HealthResponse {
  status: 'ok';
  version: string;
  timestamp: string;
}
