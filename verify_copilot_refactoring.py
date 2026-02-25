#!/usr/bin/env python3
"""
Quick verification that CopilotPenguin refactoring is working correctly.
"""
import sys
from pathlib import Path

def test_imports():
    """Test that all imports work."""
    print("Testing imports...")
    
    try:
        from penguins import CopilotPenguin
        print("✓ CopilotPenguin imported from penguins")
    except ImportError as e:
        print(f"✗ Failed to import CopilotPenguin: {e}")
        return False
    
    try:
        from penguins.copilot_penguin import DecisionLogger, TacticV1
        print("✓ DecisionLogger and TacticV1 imported from penguins.copilot_penguin")
    except ImportError as e:
        print(f"✗ Failed to import from copilot_penguin package: {e}")
        return False
    
    try:
        from penguins.copilot_penguin.tactics import BaseTactic
        print("✓ BaseTactic imported")
    except ImportError as e:
        print(f"✗ Failed to import BaseTactic: {e}")
        return False
    
    return True


def test_instantiation():
    """Test that CopilotPenguin can be instantiated."""
    print("\nTesting instantiation...")
    
    try:
        from penguins import CopilotPenguin
        penguin = CopilotPenguin()
        print(f"✓ CopilotPenguin created: {penguin.name}")
        print(f"  - Tactic: {penguin.tactic.name} v{penguin.tactic.version}")
        print(f"  - Logger: {penguin.logger.__class__.__name__}")
        return True
    except Exception as e:
        print(f"✗ Failed to create CopilotPenguin: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_decision_logging():
    """Test that decisions are logged correctly."""
    print("\nTesting decision logging...")
    
    try:
        from penguins.copilot_penguin.decision_logger import DecisionLogger
        
        logger = DecisionLogger("test.json")
        logger.current_tactic = "TestTactic"
        logger.tactic_version = "1.0"
        
        # Create a test log
        log = logger.log_decision("AAPL", 10, "BUY")
        log.price = 150.00
        log.quantity = 2
        log.reasoning = "Test buy signal"
        log.indicators = {"rsi": 60, "roc": 0.015}
        
        summary = logger.get_summary()
        print(f"✓ Decision logged successfully")
        print(f"  - Total decisions: {summary['total_decisions']}")
        print(f"  - Buy count: {summary['buy_count']}")
        print(f"  - Tactic: {summary['current_tactic']} v{summary['tactic_version']}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to log decision: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tactic_switching():
    """Test that tactics can be switched."""
    print("\nTesting tactic switching...")
    
    try:
        from penguins import CopilotPenguin
        from penguins.copilot_penguin.tactics import TacticV1
        
        penguin = CopilotPenguin()
        original_tactic = penguin.tactic.name
        
        # Switch to v1 explicitly
        tactic_v1 = TacticV1()
        penguin.switch_tactic(tactic_v1)
        
        print(f"✓ Tactic switched successfully")
        print(f"  - Original: {original_tactic}")
        print(f"  - Switched to: {penguin.tactic.name} v{penguin.tactic.version}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to switch tactic: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tactic_description():
    """Test that tactic descriptions work."""
    print("\nTesting tactic descriptions...")
    
    try:
        from penguins.copilot_penguin.tactics import TacticV1
        
        tactic = TacticV1()
        desc = tactic.get_description()
        
        print(f"✓ Tactic description retrieved:")
        for line in desc.split("\n")[:3]:
            print(f"  {line}")
        
        return True
    except Exception as e:
        print(f"✗ Failed to get tactic description: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("=" * 70)
    print("COPILOT PENGUIN REFACTORING VERIFICATION")
    print("=" * 70)
    
    all_tests = [
        test_imports,
        test_instantiation,
        test_decision_logging,
        test_tactic_switching,
        test_tactic_description,
    ]
    
    results = []
    for test in all_tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if all(results):
        print("✓ All verification tests PASSED")
        print("\nThe refactored CopilotPenguin system is ready to use!")
        print("\nTo run the simulation:")
        print("  python run_simulation.py")
        print("\nTo evaluate CopilotPenguin performance:")
        print("  python evaluate_copilot.py")
        print("=" * 70)
        return 0
    else:
        print("✗ Some tests FAILED")
        print("Please review the errors above.")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
