const js = require('@eslint/js');
const globals = require('globals');
const importPlugin = require('eslint-plugin-import');

module.exports = [
  js.configs.recommended,

  {
    files: ['src/static/js/**/*.js'],

    languageOptions: {
      parserOptions: { ecmaVersion: 2021, sourceType: 'module' },
      globals: {
        ...globals.browser,
        changePattern: 'readonly',
        copyFullDigest: 'readonly',
        copyText: 'readonly',
        downloadFullDigest: 'readonly',
        handleSubmit: 'readonly',
        posthog: 'readonly',
        submitExample: 'readonly',
        toggleAccessSettings: 'readonly',
        toggleFile: 'readonly',
        toggleTheme: 'readonly',
      },
    },

    plugins: { import: importPlugin },

    rules: {
      // Import hygiene (eslint-plugin-import)
      'import/no-extraneous-dependencies': 'error',
      'import/no-unresolved': 'error',
      'import/order': ['warn', { alphabetize: { order: 'asc' } }],

      // Safety & bug-catchers
      'consistent-return': 'error',
      'default-case': 'error',
      'no-implicit-globals': 'error',
      'no-shadow': 'error',

      // Maintainability / complexity
      complexity: ['warn', 10],
      'max-depth': ['warn', 4],
      'max-lines': ['warn', 500],
      'max-params': ['warn', 5],

      // Stylistic consistency (auto-fixable)
      'arrow-parens': ['error', 'always'],
      curly: ['error', 'all'],
      indent: ['error', 4, { SwitchCase: 2 }],
      'newline-per-chained-call': ['warn', { ignoreChainWithDepth: 2 }],
      'no-multi-spaces': 'error',
      'object-shorthand': ['error', 'always'],
      'padding-line-between-statements': [
        'warn',
        { blankLine: 'always', prev: '*', next: 'return' },
        { blankLine: 'always', prev: ['const', 'let', 'var'], next: '*' },
        { blankLine: 'any', prev: ['const', 'let', 'var'], next: ['const', 'let', 'var'] },
      ],
      'quote-props': ['error', 'consistent-as-needed'],
      quotes: ['error', 'single', { avoidEscape: true }],
      semi: 'error',

      // Modern / performance tips
      'arrow-body-style': ['warn', 'as-needed'],
      'prefer-arrow-callback': 'error',
      'prefer-exponentiation-operator': 'error',
      'prefer-numeric-literals': 'error',
      'prefer-object-has-own': 'warn',
      'prefer-object-spread': 'error',
      'prefer-template': 'error',
    },
  },
];
