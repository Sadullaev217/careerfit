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

export interface Analysis {
  id: string;
  status: AnalysisStatus;
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
