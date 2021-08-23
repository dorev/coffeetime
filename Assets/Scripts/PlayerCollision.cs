using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerCollision : MonoBehaviour
{
    public PlayerState playerState;

    private void OnTriggerEnter2D(Collider2D collision)
    {
        ProcessCollision(collision.gameObject);
    }

    private void OnCollisionEnter2D(Collision2D collision)
    {
        ProcessCollision(collision.gameObject);
    }

    void ProcessCollision(GameObject collidingObject)
    {
        if(collidingObject.CompareTag("Drinkable"))
        {
            Drinkable drinkable = collidingObject.GetComponent<Drinkable>();
            switch(drinkable.liquid)
            {
                case Drinkable.Liquid.Coffee:
                    GiveCoffee(drinkable.amount);
                    Destroy(collidingObject);
                    break;

                case Drinkable.Liquid.Water:
                    break;

                case Drinkable.Liquid.Beer:
                    break;

                default:
                    Debug.LogError("Unexpected Drinkable.Liquid value");
                    return;
            }
        }
    }
    void GiveCoffee(int amount)
    {
        playerState.RefillCoffee(amount);
    }
}
