#!/usr/bin/env node
/**
 * Generate the browser Agent contract from the running FastAPI OpenAPI surface.
 *
 * The frozen JSON is an output, never an input.  This keeps a hand-edited
 * client from concealing a server/browser contract change.
 */

import { execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const repositoryRoot = resolve(scriptDirectory, '../../../../..')
const python = join(repositoryRoot, 'backend', '.venv', 'bin', 'python')
const artifactPaths = {
  client: join('frontend', 'src', 'features', 'agent', 'api', 'client.generated.ts'),
  frozen: join('backend', 'openapi-agent-v1.json'),
  schemas: join('frontend', 'src', 'features', 'agent', 'api', 'schemas.generated.ts'),
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stable(value[key])]))
  }
  return value
}

function json(value) {
  return `${JSON.stringify(stable(value), null, 2)}\n`
}

function runtimeOpenApi() {
  if (!existsSync(python)) {
    throw new Error(`Missing backend virtualenv Python: ${relative(repositoryRoot, python)}`)
  }
  const source = [
    'import json',
    'from app.main import create_app',
    'print(json.dumps(create_app().openapi(), ensure_ascii=False))',
  ].join('; ')
  return JSON.parse(execFileSync(python, ['-c', source], { cwd: join(repositoryRoot, 'backend'), encoding: 'utf8' }))
}

function referencedComponents(value, openapi, selected = new Map()) {
  if (Array.isArray(value)) {
    value.forEach((item) => referencedComponents(item, openapi, selected))
    return selected
  }
  if (!value || typeof value !== 'object') return selected

  if (typeof value.$ref === 'string' && value.$ref.startsWith('#/components/')) {
    const [, , section, name] = value.$ref.split('/')
    const key = `${section}/${name}`
    if (!selected.has(key)) {
      const component = openapi.components?.[section]?.[name]
      if (!component) throw new Error(`OpenAPI reference is missing: ${value.$ref}`)
      selected.set(key, component)
      referencedComponents(component, openapi, selected)
    }
  }
  Object.values(value).forEach((item) => referencedComponents(item, openapi, selected))
  return selected
}

function agentContract(openapi) {
  const paths = Object.fromEntries(
    Object.entries(openapi.paths)
      .filter(([path]) => path.startsWith('/api/v1/agent/'))
      .map(([path, item]) => [path, item]),
  )
  const components = referencedComponents(paths, openapi)
  const selectedComponents = {}
  for (const [key, value] of components) {
    const [section, name] = key.split('/')
    selectedComponents[section] ??= {}
    selectedComponents[section][name] = value
  }

  for (const operation of Object.values(paths).flatMap((pathItem) => Object.values(pathItem))) {
    if (!operation || typeof operation !== 'object' || !Array.isArray(operation.security)) continue
    for (const requirement of operation.security) {
      for (const schemeName of Object.keys(requirement)) {
        const scheme = openapi.components?.securitySchemes?.[schemeName]
        if (scheme) {
          selectedComponents.securitySchemes ??= {}
          selectedComponents.securitySchemes[schemeName] = scheme
        }
      }
    }
  }

  return {
    info: { title: openapi.info.title, version: openapi.info.version },
    openapi: openapi.openapi,
    paths,
    ...(Object.keys(selectedComponents).length ? { components: selectedComponents } : {}),
  }
}

function identifier(name) {
  return name.replace(/^([A-Z]+)(?=[A-Z][a-z]|$)/, (prefix) => prefix.toLowerCase()).replace(/^./, (first) => first.toLowerCase())
}

function quoted(value) {
  return JSON.stringify(value)
}

function schemaToZod(schema) {
  if (!schema) return 'z.unknown()'
  if (schema.$ref) return `z.lazy(() => ${identifier(schema.$ref.split('/').at(-1))}Schema)`
  if (schema.enum) return `z.enum([${schema.enum.map(quoted).join(', ')}])`
  if (schema.allOf) return schema.allOf.map(schemaToZod).reduce((left, right) => `${left}.and(${right})`)

  let result
  if (schema.type === 'string') {
    result = 'z.string()'
    if (schema.format === 'uuid') result += '.uuid()'
    if (schema.minLength !== undefined) result += `.min(${schema.minLength})`
    if (schema.maxLength !== undefined) result += `.max(${schema.maxLength})`
  } else if (schema.type === 'integer') {
    result = 'z.number().int()'
    if (schema.minimum !== undefined) result += `.min(${schema.minimum})`
  } else if (schema.type === 'number') {
    result = 'z.number()'
  } else if (schema.type === 'boolean') {
    result = 'z.boolean()'
  } else if (schema.type === 'array') {
    result = `z.array(${schemaToZod(schema.items)})`
  } else if (schema.type === 'object' || schema.properties) {
    if (!schema.properties && schema.additionalProperties) {
      const valueSchema = schema.additionalProperties === true ? 'z.unknown()' : schemaToZod(schema.additionalProperties)
      result = `z.record(z.string(), ${valueSchema})`
      return schema.nullable ? `${result}.nullable()` : result
    }
    const required = new Set(schema.required ?? [])
    const fields = Object.entries(schema.properties ?? {})
      .map(([name, field]) => {
        let fieldSchema = schemaToZod(field)
        if (field.default !== undefined) fieldSchema += `.default(${JSON.stringify(field.default)})`
        if (!required.has(name)) fieldSchema += '.optional()'
        return `  ${quoted(name)}: ${fieldSchema},`
      })
      .join('\n')
    result = `z.object({\n${fields}\n})${schema.additionalProperties === false ? '.strict()' : '.passthrough()'}`
  } else {
    result = 'z.unknown()'
  }
  if (schema.nullable) result += '.nullable()'
  return result
}

function schemasSource(contract) {
  const schemas = contract.components?.schemas ?? {}
  const lines = [
    '/* This file is generated by generate-contracts.mjs. Do not edit it. */',
    "import { z } from 'zod'",
    '',
  ]
  for (const [name, schema] of Object.entries(schemas).sort(([left], [right]) => left.localeCompare(right))) {
    lines.push(`export const ${identifier(name)}Schema = ${schemaToZod(schema)}`)
    lines.push(`export type ${name} = z.infer<typeof ${identifier(name)}Schema>`)
    lines.push('')
  }
  return `${lines.join('\n')}\n`
}

function requestBody(operation) {
  const content = operation.requestBody?.content ?? {}
  const jsonSchema = content['application/json']?.schema
  if (jsonSchema) return { kind: 'json', schema: jsonSchema.$ref?.split('/').at(-1) ?? null }
  if (content['multipart/form-data']?.schema) return { kind: 'multipart', schema: null }
  return null
}

function operationResponseSchema(operation) {
  const successCode = Object.keys(operation.responses ?? {}).find((code) => /^2\d\d$/.test(code))
  const response = successCode ? operation.responses?.[successCode] : undefined
  const schema = response?.content?.['application/json']?.schema
  return schema?.$ref?.split('/').at(-1) ?? null
}

function clientSource(contract) {
  const lines = [
    '/* This file is generated by generate-contracts.mjs. Do not edit it. */',
    "import { requestWithAccess } from '@/auth/api'",
    "import type * as Contract from './schemas.generated'",
    '',
  ]
  for (const [path, pathItem] of Object.entries(contract.paths).sort(([left], [right]) => left.localeCompare(right))) {
    for (const [method, rawOperation] of Object.entries(pathItem)) {
      if (!['delete', 'get', 'patch', 'post', 'put'].includes(method) || !rawOperation || typeof rawOperation !== 'object') continue
      const operation = rawOperation
      const operationId = operation.operationId
      if (!operationId) throw new Error(`Agent operation lacks operationId: ${method.toUpperCase()} ${path}`)
      const parameters = (operation.parameters ?? []).filter((parameter) => parameter.in === 'path')
      const parameterNames = parameters.map((parameter) => parameter.name)
      const body = requestBody(operation)
      const responseType = operationResponseSchema(operation) ?? 'unknown'
      const argumentsList = ['accessToken: string', ...parameterNames.map((name) => `${identifier(name)}: string`)]
      if (body?.kind === 'json' && body.schema) argumentsList.push(`payload: Contract.${body.schema}`)
      if (body?.kind === 'multipart') argumentsList.push('image: File', 'commandKey: string')
      const browserPath = path.replace(/^\/api\/v1/, '')
      const resolvedPath = browserPath.replace(/\{([^}]+)\}/g, (_match, name) => `\${encodeURIComponent(${identifier(name)})}`)
      const initLines = [`method: '${method.toUpperCase()}'`]
      if (body?.kind === 'json' && body.schema) initLines.push("headers: { 'Content-Type': 'application/json' }", 'body: JSON.stringify(payload)')
      if (body?.kind === 'multipart') initLines.push("headers: { 'Idempotency-Key': commandKey }", "body: (() => { const form = new FormData(); form.append('image', image); return form })()")
      lines.push(`export async function ${identifier(operationId)}(${argumentsList.join(', ')}): Promise<Response> {`)
      lines.push(`  return requestWithAccess(\`${resolvedPath}\`, accessToken, { ${initLines.join(', ')} })`)
      lines.push('}')
      lines.push(`export type ${operationId}Response = ${responseType === 'unknown' ? 'unknown' : `Contract.${responseType}`}`)
      lines.push('')
    }
  }
  return `${lines.join('\n')}\n`
}

function writeArtifacts(root) {
  const contract = agentContract(runtimeOpenApi())
  const output = {
    [artifactPaths.frozen]: json(contract),
    [artifactPaths.schemas]: schemasSource(contract),
    [artifactPaths.client]: clientSource(contract),
  }
  for (const [path, content] of Object.entries(output)) {
    const target = join(root, path)
    mkdirSync(dirname(target), { recursive: true })
    writeFileSync(target, content, 'utf8')
  }
  return output
}

function generateAll() {
  writeArtifacts(repositoryRoot)
}

function checkAll() {
  const temporaryRoot = mkdtempSync(join(tmpdir(), 'food-agent-contract-'))
  try {
    const generated = writeArtifacts(temporaryRoot)
    const drift = Object.keys(generated).filter((path) => {
      const committed = join(repositoryRoot, path)
      return !existsSync(committed) || readFileSync(committed, 'utf8') !== readFileSync(join(temporaryRoot, path), 'utf8')
    })
    if (drift.length) {
      throw new Error(`Agent API contract drift detected: ${drift.join(', ')}. Run generate-all and commit every artifact.`)
    }
  } finally {
    rmSync(temporaryRoot, { force: true, recursive: true })
  }
}

const command = process.argv[2]
if (command === 'generate-all') generateAll()
else if (command === 'check-all') checkAll()
else throw new Error('Usage: node generate-contracts.mjs generate-all|check-all')
