const jest = require('jest');

module.exports = {
  preset: 'jest-environment-jsdom',
  testEnvironment: 'jsdom',
  testPathIgnorePatterns: ['/node_modules/'],
  testMatch: ['**/*.test.js'],
  moduleFileExtensions: ['js', 'json'],
  transform: {
    '\.js$': 'babel-jest',
  },
  transformIgnorePatterns: ['/node_modules/'],
  setupFilesAfterEnv: ['<rootDir>/setupTests.js'],
  testEnvironmentOptions: {
    url: 'http://localhost',
  },
  collectCoverage: true,
  coverageDirectory: 'coverage/',
  coverageReporters: ['json', 'text', 'lcov', 'clover'],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
  moduleDirectories: ['node_modules'],
  modulePaths: ['<rootDir>/src'],
  moduleNameMapper: {
    '\^\\.(css|less|scss|sass)$': 'identity-obj-proxy',
  },
  testTimeout: 10000,
  setupFiles: ['<rootDir>/setupTests.js'],
  snapshotSerializers: ['jest-serializer-jpg'],
  testPathDirs: ['<rootDir>/tests'],
  testPathPatters: ['**/*.test.js'],
  testRegex: '.*\.test\.js$'
};