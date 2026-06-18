---
paths:
  - "src/**/*.ts"
  - "src/**/*.tsx"
---

# HAL Coding Standards /app

## 1. Hook / Component Separation

- All component logic (useState, useEffect, useCallback, useMemo, data fetching, event handlers) goes in a dedicated hook file: `src/hooks/use-<name>.ts` or the nearest `hooks/` directory.
- The `.tsx` file contains only JSX and calls the hook. If you find yourself adding logic to a `.tsx` file, consider whether it should be a new component or extracted to a hook.
- Do not mix presentation and logic in the same file.
- Do not use inline functions in JSX props — extract them to hooks or separate components.
- Do not use `useCallback` for simple getters or pure calculations.
- Do not use `useMemo` for simple calculations — only for expensive operations.
- Do not use `useRef` for state management — use `useState` instead.
- Do not use `useEffect` for simple side effects — use `useCallback` or `useMemo` instead.
- Do not use `useState` for complex state management — use a state management library like Zustand or Redux.
- Do not use `useContext` for simple state management — use a state management library like Zustand or Redux.
- Do not use `useReducer` for simple state management — use a state management library like Zustand or Redux.
- Do not use `useLayoutEffect` — use `useEffect` instead.
- Do not use `useImperativeHandle` — use `useRef` instead.
- Do not use `useDebugValue` — use `useEffect` instead.
- Do not use `useId` — use `useRef` instead.
- Do not use `useTransition` — use `useState` instead.
- Do not use `useDeferredValue` — use `useState` instead.

**Example:**

```
components/slider.tsx         → JSX only, calls useSlider()
lib/hooks/use-slider.ts       → all state and logic
```

## 2. TypeScript Types in /types/

- If a file declares more than one `type` or `interface`, those declarations must be moved to a dedicated file in `src/types/`.
- `src/types/index.ts` must re-export all type files.
- Do not create circular dependencies (e.g. a types file importing from a hook file).

**Example:** `src/types/slider.ts` — not inline in the component or hook.

## 3. Tailwind CSS Only — No StyleSheet.create

- Use Tailwind CSS `className` for all component styling. Do **not** use `StyleSheet.create()`.
- For React Native APIs that require a plain style object (e.g. `RenderHTML` `tagsStyles`, `HTMLView` `stylesheet`), use a plain JS object literal — not `StyleSheet.create()`.
- For truly dynamic values that cannot be expressed in Tailwind (e.g. `height: SCREEN_HEIGHT`), use an inline `style={{}}` prop alongside `className`.

## 4. No `any` Type

- Never use `any` in hand-written TypeScript files. Use `unknown`, a specific type, or a generic instead.

## 5. Naming Conventions

- **Components:** PascalCase (`TaskHeader`, `ChallengeCard`)
- **Hooks:** camelCase prefixed with `use` (`useTaskContent`, `useManualWorkout`)
- **State variables:** camelCase; booleans prefixed with `is` / `has` (`isLoading`, `hasError`)
- **State setters:** `set` + PascalCase noun (`setIsLoading`, `setUser`)
- **Functions / event handlers:** camelCase verbs (`handlePress`, `fetchData`, `formatDate`)
- **Variables:** camelCase
- **Types / Interfaces:** PascalCase (`ManualWorkoutForm`, `TaskContentProps`)
- **Files:** kebab-case (`task-content.tsx`, `use-task-content.ts`)

## 6. Import / Export Conventions

- Named exports for components, hooks, utilities, and types.
- Default exports only for route/screen files (Expo Router convention).
- Group imports: external packages → internal `@/src/` aliases → relative paths. Separate each group with a blank line.
- No barrel re-exports that create circular dependencies.

## 8. State Management

- Use **Zustand** for all global and shared state. Do not use React Context or Redux for app state.
- Store files live in `src/stores/<featureStore>.ts`.
- Define the store's state interface locally in the store file (this is an exception to the types rule — store-internal state types stay co-located).
- Expose state and actions together in a single `create()` call.
- Use the `useStore` selector pattern to avoid unnecessary re-renders: `const value = useMyStore(state => state.value)`.

**Example:**

```
src/stores/accountsStore.ts
src/stores/creditsStore.ts
```

## 7. Translations

- All user-visible text must use the `t()` function from `react-i18next`.
- Add the translation key and English value to the appropriate translations object.
- Never hardcode English strings directly in JSX (e.g. `"Submit"`, `"Cancel"`, `"Error"`).

**Example:**

```tsx
// ✅ correct
<Text>{t('common.submit')}</Text>

// ❌ wrong
<Text>Submit</Text>
```

## 9. Code Review (after completing a new feature)

After implementing a new feature, perform a self-review before marking it ready for PR. Use these principles:

### Focus areas (in order)

1. **Architecture first** — Does the change fit cleanly into the existing system? Check hook/component separation, store usage, and type placement before reviewing details.
2. **Naming** — Names are read far more than written. Every variable, function, and file name should accurately convey its purpose without needing a comment.
3. **Logic and edge cases** — Run the code locally. Static analysis misses runtime behavior. Test the happy path and obvious failure modes.

### What to catch

- Logic errors, missing edge cases, and incorrect assumptions
- Code that violates the standards in this file (any types, hardcoded strings, StyleSheet.create, etc.)
- Unnecessary complexity — if a simpler approach exists, prefer it
- Missing or incorrect translations
- TypeScript errors (run `npm run type-check` before declaring done)
- **Debug/test code** — remove all `console.log`, `console.warn`, `console.error`, temporary mock data, debug flags, and commented-out code before marking a task complete

### What to skip

- Formatting, whitespace, and style — let the linter handle it
- Nitpicks that don't affect correctness, readability, or maintainability

### When leaving review comments (PR reviews)

- Explain _why_ something should change, not just _what_ to change
- Suggest an alternative when rejecting an approach
- Ask questions rather than assuming intent for unclear code
- Be direct — vague feedback blocks progress
- Separate blocking issues from non-blocking suggestions (e.g. prefix non-blocking with "nit:")

### Any new Hal features should be implemented with the same attention to detail and adherence to these standards. Any new commands should be ADDED TO THE README.