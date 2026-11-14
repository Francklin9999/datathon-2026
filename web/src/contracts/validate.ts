/** Validate unknown JSON before use. Additional fields are accepted for v1 compatibility. */
import { Ajv2020, type ErrorObject, type ValidateFunction } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import schema from '../../../contracts/generated/schema.json' with { type: 'json' };
import type { AplombContracts } from './types.js';

const ajv = new Ajv2020({
  allErrors: true, strict: false, strictNumbers: true, validateFormats: true,
});
addFormats(ajv);
ajv.addSchema(schema);
const validators = new Map<string, ValidateFunction>();

export class ContractValidationError extends Error {
  constructor(readonly contract: string, readonly issues: readonly ErrorObject[]) {
    super(`Invalid ${contract}: ${ajv.errorsText([...issues])}`);
    this.name = 'ContractValidationError';
  }
}

export function validateContract<K extends keyof AplombContracts>(
  name: K, value: unknown,
): AplombContracts[K] {
  let validate = validators.get(name);
  if (!validate) {
    validate = ajv.compile({ $ref: `${schema.$id}#/$defs/${name}` });
    validators.set(name, validate);
  }
  if (!validate(value)) throw new ContractValidationError(name, validate.errors ?? []);
  return value as AplombContracts[K];
}
