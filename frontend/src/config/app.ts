/**
 * Application-wide, non-secret configuration.
 */
const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

export const APP_NAME = 'CodeSentinel'
export const APP_VERSION = '0.1.0'
export const REPOSITORY_URL = 'https://github.com/zhangyu1108l/CodeSentinel'

/**
 * Empty base URL means same-origin requests. During development the
 * Vite proxy forwards `/api` to the Spring Boot service.
 */
export const API_BASE_URL = rawApiBaseUrl.replace(/\/+$/, '')
