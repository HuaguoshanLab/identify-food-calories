import { z } from 'zod'

const passwordSchema = z
  .string()
  .min(12, '密码至少需要 12 个字符。')
  .max(128, '密码不能超过 128 个字符。')

const emailSchema = z.string().email('请输入有效的邮箱地址。')

export const loginSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
})

export const registerSchema = loginSchema
  .extend({ confirmPassword: z.string() })
  .refine((value) => value.password === value.confirmPassword, {
    message: '两次输入的密码不一致。',
    path: ['confirmPassword'],
  })

export const verificationCodeSchema = z.object({
  code: z.string().regex(/^[0-9]{6}$/, '请输入 6 位数字验证码。'),
})

export const forgotPasswordSchema = z.object({ email: emailSchema })

export const resetPasswordSchema = verificationCodeSchema
  .extend({
    password: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((value) => value.password === value.confirmPassword, {
    message: '两次输入的密码不一致。',
    path: ['confirmPassword'],
  })

export type LoginValues = z.infer<typeof loginSchema>
export type RegisterValues = z.infer<typeof registerSchema>
export type VerificationCodeValues = z.infer<typeof verificationCodeSchema>
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>
